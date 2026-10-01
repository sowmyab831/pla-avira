"""Health routes: lab results, medical records, health tracking."""
import logging
import io
import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from app.routes.auth import get_current_user
from app.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.private_scope import resolve_private_scope
import pdfplumber
import re
from app.config import settings
from app.services.file_storage import get_file_storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/health", tags=["health"])

# In-memory storage for health reports (shared with chat)
health_reports_store: List[Dict[str, Any]] = []
lab_results_store: List[Dict[str, Any]] = []

# Persist health state across restarts
HEALTH_STATE_FILE = Path(os.environ.get("AVIRA_DATA_DIR", "/data/documents")) / "health_state.json"


def _save_health_state():
    try:
        with open(HEALTH_STATE_FILE, 'w') as f:
            json.dump({"reports": health_reports_store, "lab_results": lab_results_store}, f, default=str)
    except Exception as e:
        logger.error(f"Failed to save health state: {e}")


def _load_health_state():
    global health_reports_store, lab_results_store
    if HEALTH_STATE_FILE.exists():
        try:
            with open(HEALTH_STATE_FILE, 'r') as f:
                data = json.load(f)
                health_reports_store = data.get("reports", [])
                # Backfill user_id and report_date for old reports
                for r in health_reports_store:
                    if not r.get("user_id"):
                        file_id = r.get("file_id", "")
                        parts = file_id.split("_") if file_id else []
                        if len(parts) >= 3 and parts[0] == "health":
                            r["user_id"] = parts[1]
                        else:
                            r["user_id"] = "default"
                    if not r.get("report_date"):
                        r["report_date"] = r.get("uploaded_at", datetime.now().isoformat())[:10]
                # Keep reports sorted by document date
                health_reports_store.sort(key=lambda r: r.get("report_date") or r.get("uploaded_at", ""))
                lab_results_store = data.get("lab_results", [])
        except Exception as e:
            logger.error(f"Failed to load health state: {e}")


_load_health_state()


class LabResult(BaseModel):
    """Lab result model."""
    test_name: str
    value: float
    unit: str
    reference_range: str
    is_abnormal: bool = False
    date: str


class HealthAlert(BaseModel):
    """Health alert model."""
    alert_type: str  # "high", "low", "critical"
    test_name: str
    value: float
    threshold: float
    message: str


class HealthReport(BaseModel):
    """Health report model."""
    lab_results: List[LabResult]
    alerts: List[HealthAlert]
    last_updated: str


# Reference ranges for common tests (comprehensive)
REFERENCE_RANGES = {
    "glucose": {"min": 70, "max": 100, "unit": "mg/dL"},
    "cholesterol": {"min": 0, "max": 200, "unit": "mg/dL"},
    "ldl": {"min": 0, "max": 100, "unit": "mg/dL"},
    "hdl": {"min": 40, "max": 999, "unit": "mg/dL"},
    "triglycerides": {"min": 0, "max": 150, "unit": "mg/dL"},
    "hemoglobin": {"min": 13.5, "max": 17.5, "unit": "g/dL"},
    "hematocrit": {"min": 41, "max": 53, "unit": "%"},
    # CBC tests
    "hb_estimation": {"min": 130, "max": 170, "unit": "g/l"},
    "pcv": {"min": 0.4, "max": 0.5, "unit": "l/l"},
    "rbc_count": {"min": 4.5, "max": 5.5, "unit": "x10^12/l"},
    "total_wbc_count": {"min": 4.0, "max": 10.0, "unit": "x10^9/l"},
    "platelet_count": {"min": 150, "max": 410, "unit": "x10^9/l"},
    "neutrophils": {"min": 40, "max": 80, "unit": "%"},
    "lymphocytes": {"min": 20, "max": 40, "unit": "%"},
    "monocytes": {"min": 2, "max": 10, "unit": "%"},
    "eosinophils": {"min": 1, "max": 6, "unit": "%"},
    "basophils": {"min": 0, "max": 2, "unit": "%"},
    "mcv": {"min": 80, "max": 100, "unit": "fL"},
    "mch": {"min": 27.3, "max": 32.3, "unit": "pg"},
    "mchc": {"min": 315, "max": 345, "unit": "g/l"},
    "rdw": {"min": 11.6, "max": 14.5, "unit": "%"},
}




@router.post("/upload-lab-results")
async def upload_lab_results(files: List[UploadFile] = File(...), user_id: str = "default", user=Depends(get_current_user), db: AsyncSession = Depends(get_session)) -> dict:
    """
    Upload and parse one or more lab results PDFs.

    Detects abnormal values and generates health alerts.

    HIPAA ADVISORY: This endpoint processes health data (PHI).
    - All data is masked before external LLM calls
    - Data is encrypted at rest and in transit (TLS)
    - Audit logging is enabled
    - Do NOT send raw PHI to non-compliant external services
    """
    all_lab_results: List[Dict[str, Any]] = []
    all_alerts: List[Dict[str, Any]] = []
    file_ids: List[str] = []
    uploaded_files: List[str] = []
    user_id = await resolve_private_scope(user_id, user, db)

    try:
        for file in files:
            content = await file.read()

            if not file.filename or not file.filename.endswith(".pdf"):
                raise HTTPException(status_code=400, detail="Only PDF files supported")

            if len(content) > settings.max_upload_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"{file.filename} exceeds the "
                           f"{settings.max_upload_bytes // (1024*1024)}MB upload limit"
                )

            # Save file to persistent storage
            storage = get_file_storage()
            file_id = storage.save_file(
                file_content=content,
                filename=file.filename,
                category="health",
                user_id=user_id,
                metadata={"type": "lab_results"}
            )
            file_ids.append(file_id)
            uploaded_files.append(file.filename)

            report_date, lab_results = _parse_lab_pdf(content)
            alerts = _generate_health_alerts(lab_results)

            # Store results for later access
            global health_reports_store, lab_results_store
            report = {
                "id": f"report_{datetime.now().timestamp()}",
                "user_id": user_id,
                "file_id": file_id,
                "filename": file.filename,
                "report_date": report_date,
                "lab_results": [r.dict() for r in lab_results],
                "alerts": [a.dict() for a in alerts],
                "uploaded_at": datetime.now().isoformat(),
            }
            health_reports_store.append(report)
            lab_results_store.extend([{**r.dict(), "user_id": user_id} for r in lab_results])

            all_lab_results.extend([r.dict() for r in lab_results])
            all_alerts.extend([a.dict() for a in alerts])

            logger.info(f"Parsed {len(lab_results)} lab results, {len(alerts)} alerts, saved as {file_id}")

        # Build report text for AI analysis
        report_lines = [f"- {r['test_name']}: {r['value']} {r['unit']} (ref: {r['reference_range']}, status: {'abnormal' if r['is_abnormal'] else 'normal'})" for r in all_lab_results]
        alert_lines = [f"- {a['test_name']}: {a['message']}" for a in all_alerts]
        report_text = "Lab Results:\n" + "\n".join(report_lines)
        if alert_lines:
            report_text += "\n\nAlerts:\n" + "\n".join(alert_lines)

        # Run LLM analysis on the combined report (skip if nothing was parsed)
        if all_lab_results:
            from app.services.health_analyzer import get_health_analyzer
            analyzer = get_health_analyzer()
            # Use the faster model for health report analysis so the UI stays responsive
            analysis = await analyzer.analyze_health_report(
                report_text=report_text,
                report_type="blood_test",
                ollama_host=settings.ollama_host,
                ollama_model=settings.ollama_fast_model or settings.ollama_model
            )
        else:
            analysis = None

        for r in health_reports_store[-len(files):]:
            r["analysis"] = analysis

        # Order reports chronologically by the document's own generation date
        health_reports_store.sort(key=lambda r: r.get("report_date") or r.get("uploaded_at", ""))
        _save_health_state()

        return {
            "file_ids": file_ids,
            "uploaded_files": uploaded_files,
            "lab_results": all_lab_results,
            "alerts": all_alerts,
            "analysis": analysis,
            "last_updated": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing lab results: {e}")
        raise HTTPException(status_code=400, detail=f"Could not parse lab results: {e}")


def _parse_lab_pdf(content: bytes) -> tuple[str, List[LabResult]]:
    """Parse lab results from PDF - returns (report_date, lab_results)."""
    results = []
    report_date = datetime.now().strftime("%Y-%m-%d")

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

            # Try to extract the report generation date from the PDF text
            date_patterns = [
                (r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})', "%d %B %Y"),
                (r'(\d{1,2}\s+\w{3}\s+\d{4})', "%d %b %Y"),
                (r'(\d{4}-\d{2}-\d{2})', "%Y-%m-%d"),
                (r'(\d{2}/\d{2}/\d{4})', "%d/%m/%Y"),
                (r'(\d{2}/\d{2}/\d{4})', "%m/%d/%Y"),
            ]
            for pattern, fmt in date_patterns:
                m = re.search(pattern, full_text)
                if m:
                    try:
                        report_date = datetime.strptime(m.group(1), fmt).strftime("%Y-%m-%d")
                        break
                    except (ValueError, TypeError):
                        continue

            # Pattern 1: Table format - "TEST NAME. value [H/L] unit min - max"
            # Example: "HB ESTIMATION. 119 [L] g/l 130 - 170"
            pattern1 = r"([A-Z][A-Z\s\(\)]+?)\.?\s+([\d.]+)\s*(?:\[([HL])\])?\s*([a-zA-Z%/\^0-9]+)\s+([\d.]+)\s*-\s*([\d.]+)"
            
            for match in re.finditer(pattern1, full_text):
                test_name = match.group(1).strip()
                value = float(match.group(2))
                flag = match.group(3)  # H or L or None
                unit = match.group(4)
                ref_min = float(match.group(5))
                ref_max = float(match.group(6))
                
                is_abnormal = flag is not None or value < ref_min or value > ref_max
                
                results.append(LabResult(
                    test_name=test_name,
                    value=value,
                    unit=unit,
                    reference_range=f"{ref_min} - {ref_max}",
                    is_abnormal=is_abnormal,
                    date=report_date,
                ))
            
            # Pattern 2: Simpler format - "Test Name value unit (range)"
            if not results:
                pattern2 = r"([A-Za-z][A-Za-z\s]+)\s+([\d.]+)\s+([a-zA-Z%/]+)\s+\(([\d.]+-[\d.]+)\)"
                for match in re.finditer(pattern2, full_text):
                    results.append(LabResult(
                        test_name=match.group(1).strip(),
                        value=float(match.group(2)),
                        unit=match.group(3),
                        reference_range=match.group(4),
                        is_abnormal=False,
                        date=report_date,
                    ))
            
            # Pattern 3: Lipid panel format - "Cholesterol: 200 mg/dL"
            if not results:
                pattern3 = r"(Cholesterol|Triglycerides|HDL|LDL|Glucose|HbA1c)[:\s]+([\d.]+)\s*([a-zA-Z%/]+)"
                for match in re.finditer(pattern3, full_text, re.I):
                    results.append(LabResult(
                        test_name=match.group(1),
                        value=float(match.group(2)),
                        unit=match.group(3),
                        reference_range="See reference",
                        is_abnormal=False,
                        date=report_date,
                    ))
        
        logger.info(f"Parsed {len(results)} lab results from PDF (report_date={report_date})")
        return report_date, results

    except Exception as e:
        logger.error(f"PDF parsing error: {e}")
        return report_date, []


def _generate_health_alerts(results: List[LabResult]) -> List[HealthAlert]:
    """Generate health alerts for abnormal values."""
    alerts = []
    
    for result in results:
        test_key = result.test_name.lower().replace(" ", "_")
        
        if test_key in REFERENCE_RANGES:
            ref = REFERENCE_RANGES[test_key]
            
            if result.value < ref["min"]:
                result.is_abnormal = True
                alerts.append(HealthAlert(
                    alert_type="low",
                    test_name=result.test_name,
                    value=result.value,
                    threshold=ref["min"],
                    message=f"{result.test_name} is LOW ({result.value} {result.unit}). Normal: {ref['min']}-{ref['max']}",
                ))
            elif result.value > ref["max"]:
                result.is_abnormal = True
                alert_type = "critical" if result.value > ref["max"] * 1.5 else "high"
                alerts.append(HealthAlert(
                    alert_type=alert_type,
                    test_name=result.test_name,
                    value=result.value,
                    threshold=ref["max"],
                    message=f"{result.test_name} is HIGH ({result.value} {result.unit}). Normal: {ref['min']}-{ref['max']}",
                ))
    
    return alerts


@router.get("/report")
async def get_health_report(user_id: str = "default", user=Depends(get_current_user), db: AsyncSession = Depends(get_session)) -> dict:
    """Get the most recent health report for user, sorted by document date."""
    user_id = await resolve_private_scope(user_id, user, db)
    user_reports = [r for r in health_reports_store if r.get("user_id") == user_id]
    if user_reports:
        user_reports.sort(key=lambda r: r.get("report_date") or r.get("uploaded_at", ""))
        return user_reports[-1]
    return {
        "lab_results": [],
        "alerts": [],
        "last_updated": datetime.now().isoformat(),
    }


@router.get("/files")
async def list_health_files(user_id: str = "default", user=Depends(get_current_user), db: AsyncSession = Depends(get_session)) -> dict:
    """List all uploaded health documents."""
    user_id = await resolve_private_scope(user_id, user, db)
    storage = get_file_storage()
    files = storage.list_files(category="health", user_id=user_id)
    return {
        "files": files,
        "count": len(files)
    }


@router.post("/analyze")
async def analyze_health_report(
    report_text: str,
    report_type: str = "general",
    user_id: str = "default"
) -> dict:
    """
    AI-powered health report analysis with doctor recommendations.
    
    Provides:
    - Report summary
    - Key findings
    - Health status assessment
    - Doctor recommendations
    - Improvement suggestions
    
    DISCLAIMER: This is AI analysis for informational purposes only.
    Always consult licensed healthcare professionals.
    """
    from app.services.health_analyzer import get_health_analyzer

    analyzer = get_health_analyzer()
    analysis = await analyzer.analyze_health_report(
        report_text=report_text,
        report_type=report_type,
        ollama_host=settings.ollama_host,
        ollama_model=settings.ollama_model
    )
    
    return analysis


@router.get("/doctors")
async def get_doctor_directory(specialty: Optional[str] = None) -> dict:
    """Get directory of doctors by specialty."""
    from app.services.health_analyzer import get_health_analyzer
    
    analyzer = get_health_analyzer()
    doctors = analyzer.get_doctor_directory(specialty)
    
    return {
        "success": True,
        "doctors": doctors,
        "count": len(doctors)
    }


@router.post("/reminder")
async def set_health_reminder(user_id: str, reminder_type: str, date: str) -> dict:
    """Set health reminder (e.g., annual checkup, medication refill)."""
    # TODO: Store in database, integrate with notification system
    return {"status": "reminder_set", "reminder_type": reminder_type, "date": date}


# ── Medical Document Photo Upload ────────────────────────────────────────────

@router.post("/upload-image")
async def upload_health_image(
    file: UploadFile = File(...),
    user_id: str = "default",
    document_type: str = "auto",
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """
    Upload a photo of a medical document (lab report, doctor's note, prescription, etc.)
    OCR extracts text, then AI analyzes it for findings and recommendations.

    HIPAA ADVISORY: This endpoint processes health data (PHI).
    - All data is masked before external LLM calls
    - Data is encrypted at rest and in transit (TLS)
    - Do NOT send raw PHI to non-compliant external services
    """
    user_id = await resolve_private_scope(user_id, user, db)
    try:
        content = await file.read()

        if len(content) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the "
                       f"{settings.max_upload_bytes // (1024*1024)}MB upload limit"
            )

        # Save file
        storage = get_file_storage()
        file_id = storage.save_file(
            file_content=content,
            filename=file.filename,
            category="health",
            user_id=user_id,
            metadata={"type": "medical_image", "document_type": document_type}
        )

        # Run OCR + analysis pipeline
        from app.services.document_ocr import get_ocr_service
        from app.services.health_analyzer import get_health_analyzer

        ocr = get_ocr_service()
        ocr_result = await ocr.analyze_image(content, document_type=document_type, user_id=user_id)

        if not ocr_result.get("success", False):
            return {
                "success": False,
                "file_id": file_id,
                "error": ocr_result.get("error", "OCR failed"),
                "ocr_text": ocr_result.get("ocr_text", "")[:500],
            }

        # AI health analysis on extracted text
        analyzer = get_health_analyzer()
        analysis = await analyzer.analyze_health_report(
            report_text=ocr_result.get("ocr_text", ""),
            report_type=ocr_result.get("document_type", "general"),
            ollama_host=settings.ollama_host,
            ollama_model=settings.ollama_model,
        )

        # Store result
        global health_reports_store
        report = {
            "id": f"report_{datetime.now().timestamp()}",
            "user_id": user_id,
            "file_id": file_id,
            "filename": file.filename,
            "document_type": ocr_result.get("document_type", "general"),
            "ocr_text": ocr_result.get("ocr_text", "")[:2000],
            "analysis": analysis,
            "uploaded_at": datetime.now().isoformat(),
        }
        health_reports_store.append(report)
        _save_health_state()

        return {
            "success": True,
            "file_id": file_id,
            "document_type": ocr_result.get("document_type", "general"),
            "ocr_preview": ocr_result.get("ocr_text", "")[:500],
            "analysis": analysis,
        }

    except Exception as e:
        logger.error(f"Health image upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
async def list_health_documents(user_id: str = "default", user=Depends(get_current_user), db: AsyncSession = Depends(get_session)) -> dict:
    """List all uploaded health/medical documents with analysis, sorted by document date."""
    user_id = await resolve_private_scope(user_id, user, db)
    docs = [r for r in health_reports_store if r.get("user_id") == user_id]
    docs.sort(key=lambda r: r.get("report_date") or r.get("uploaded_at", ""))
    return {
        "success": True,
        "documents": docs[-20:],
        "count": len(docs),
    }


@router.delete("/documents/{report_id}")
async def delete_health_document(report_id: str, user_id: str = "default", user=Depends(get_current_user), db: AsyncSession = Depends(get_session)) -> dict:
    """Delete a health document/report and its stored file."""
    global health_reports_store, lab_results_store
    user_id = await resolve_private_scope(user_id, user, db)
    idx = next((i for i, r in enumerate(health_reports_store) if r.get("id") == report_id and r.get("user_id") == user_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Document not found")

    report = health_reports_store.pop(idx)
    storage = get_file_storage()
    file_id = report.get("file_id")
    if file_id:
        try:
            storage.delete_file(file_id)
        except Exception as e:
            logger.warning(f"Failed to delete health file {file_id}: {e}")

    # Rebuild lab results from remaining reports
    lab_results_store = [
        {**lr, "user_id": r.get("user_id")}
        for r in health_reports_store
        for lr in r.get("lab_results", [])
    ]
    _save_health_state()

    return {"success": True, "deleted": report_id}


@router.get("/timeline")
async def get_health_timeline(user_id: str = "default", user=Depends(get_current_user), db: AsyncSession = Depends(get_session)) -> dict:
    """Return all health reports in chronological order plus per-test value trends."""
    user_id = await resolve_private_scope(user_id, user, db)
    docs = [r for r in health_reports_store if r.get("user_id") == user_id]
    docs.sort(key=lambda r: r.get("report_date") or r.get("uploaded_at", ""))

    trends: Dict[str, Any] = {}
    for r in docs:
        date = r.get("report_date") or r.get("uploaded_at", "")[:10]
        for lr in r.get("lab_results", []):
            name = lr.get("test_name")
            if not name:
                continue
            trends.setdefault(name, []).append({
                "date": date,
                "value": lr.get("value"),
                "unit": lr.get("unit"),
                "reference_range": lr.get("reference_range"),
                "is_abnormal": lr.get("is_abnormal"),
            })

    # Add simple direction (increasing/decreasing/stable) when multiple values exist
    for name, series in trends.items():
        series.sort(key=lambda x: x["date"])
        if len(series) >= 2:
            latest = series[-1]["value"]
            prev = series[-2]["value"]
            try:
                if latest is not None and prev is not None:
                    if float(latest) > float(prev):
                        series[-1]["direction"] = "increasing"
                    elif float(latest) < float(prev):
                        series[-1]["direction"] = "decreasing"
                    else:
                        series[-1]["direction"] = "stable"
            except (ValueError, TypeError):
                pass

    return {
        "success": True,
        "reports": docs[-20:],
        "trends": trends,
        "count": len(docs),
    }


@router.get("/summary")
async def get_health_summary(user_id: str = "default", user=Depends(get_current_user), db: AsyncSession = Depends(get_session)) -> dict:
    """Generate an AI-powered overall health summary across all reports."""
    user_id = await resolve_private_scope(user_id, user, db)
    docs = [r for r in health_reports_store if r.get("user_id") == user_id]
    docs.sort(key=lambda r: r.get("report_date") or r.get("uploaded_at", ""))

    if not docs:
        return {
            "success": True,
            "summary": "No health reports found. Upload a lab report to get a summary.",
            "structured": {},
        }

    from app.services.health_analyzer import get_health_analyzer

    analyzer = get_health_analyzer()
    result = await analyzer.generate_health_summary(
        reports=docs,
        ollama_host=settings.ollama_host,
        ollama_model=settings.ollama_fast_model or settings.ollama_model
    )
    return result
