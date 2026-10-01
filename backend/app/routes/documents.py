"""
Document Upload and Analysis Routes
Supports health reports, bank statements, receipts with OCR
"""
import logging
import base64
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.database import get_session, DocumentAnalysisDB
from app.middleware.subscription_gate import soft_rate_limit
from app.services.document_ocr import get_ocr_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


class DocumentUploadResponse(BaseModel):
    success: bool
    document_id: Optional[int] = None
    document_type: str = ""
    summary: str = ""
    extracted_data: dict = {}
    error: Optional[str] = None


class Base64UploadRequest(BaseModel):
    """For mobile app uploads with base64 encoded images."""
    image_data: str  # Base64 encoded
    document_type: str = "auto"
    file_name: str = "upload.jpg"
    user_id: str = "default"


@router.post("/upload", response_model=DocumentUploadResponse, dependencies=[Depends(soft_rate_limit("documents"))])
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form("auto"),
    user_id: str = Form("default"),
    db: AsyncSession = Depends(get_session)
):
    """
    Upload and analyze a document (image or PDF).
    Supports: JPG, PNG, PDF
    Document types: health, finance, receipt, auto (auto-detect)
    """
    try:
        # Validate file type
        allowed_types = ["image/jpeg", "image/png", "image/jpg", "application/pdf"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
            )
        
        # Read file
        file_data = await file.read()
        
        if len(file_data) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=400, detail="File too large. Max 10MB.")
        
        ocr_service = get_ocr_service()
        
        # Process based on file type
        if file.content_type == "application/pdf":
            result = await ocr_service.analyze_pdf(file_data, document_type, user_id)
        else:
            result = await ocr_service.analyze_image(file_data, document_type, user_id)
        
        if not result.get("success"):
            return DocumentUploadResponse(
                success=False,
                error=result.get("error", "Analysis failed")
            )
        
        # Save to database
        doc_record = DocumentAnalysisDB(
            user_id=user_id,
            document_type=result.get("document_type", document_type),
            file_name=file.filename or "upload",
            ocr_text=result.get("ocr_text", "")[:10000],
            analysis_summary=result.get("summary", ""),
            extracted_data=result.get("extracted_data", {}),
            confidence_score=result.get("confidence", 0.0),
            status="completed"
        )
        
        db.add(doc_record)
        await db.commit()
        await db.refresh(doc_record)
        
        return DocumentUploadResponse(
            success=True,
            document_id=doc_record.id,
            document_type=result.get("document_type", document_type),
            summary=result.get("summary", ""),
            extracted_data=result.get("extracted_data", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload error: {e}")
        return DocumentUploadResponse(success=False, error=str(e))


@router.post("/upload-base64", response_model=DocumentUploadResponse, dependencies=[Depends(soft_rate_limit("documents"))])
async def upload_document_base64(
    request: Base64UploadRequest,
    db: AsyncSession = Depends(get_session)
):
    """
    Upload document as base64 (for mobile app camera/photo library).
    """
    try:
        # Decode base64
        try:
            # Handle data URL format
            if "," in request.image_data:
                image_data = base64.b64decode(request.image_data.split(",")[1])
            else:
                image_data = base64.b64decode(request.image_data)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 image data")
        
        if len(image_data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image too large. Max 10MB.")
        
        ocr_service = get_ocr_service()
        
        # Analyze image
        result = await ocr_service.analyze_image(
            image_data, 
            request.document_type, 
            request.user_id
        )
        
        if not result.get("success"):
            return DocumentUploadResponse(
                success=False,
                error=result.get("error", "Analysis failed")
            )
        
        # Save to database
        doc_record = DocumentAnalysisDB(
            user_id=request.user_id,
            document_type=result.get("document_type", request.document_type),
            file_name=request.file_name,
            ocr_text=result.get("ocr_text", "")[:10000],
            analysis_summary=result.get("summary", ""),
            extracted_data=result.get("extracted_data", {}),
            confidence_score=result.get("confidence", 0.0),
            status="completed"
        )
        
        db.add(doc_record)
        await db.commit()
        await db.refresh(doc_record)
        
        return DocumentUploadResponse(
            success=True,
            document_id=doc_record.id,
            document_type=result.get("document_type", request.document_type),
            summary=result.get("summary", ""),
            extracted_data=result.get("extracted_data", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Base64 upload error: {e}")
        return DocumentUploadResponse(success=False, error=str(e))


@router.get("/list")
async def list_documents(
    user_id: str = "default",
    document_type: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_session)
):
    """List user's analyzed documents."""
    try:
        query = select(DocumentAnalysisDB).filter(
            DocumentAnalysisDB.user_id == user_id
        )
        
        if document_type:
            query = query.filter(DocumentAnalysisDB.document_type == document_type)
        
        query = query.order_by(DocumentAnalysisDB.upload_date.desc()).limit(limit)
        
        result = await db.execute(query)
        docs = result.scalars().all()
        
        return {
            "success": True,
            "count": len(docs),
            "documents": [
                {
                    "id": doc.id,
                    "document_type": doc.document_type,
                    "file_name": doc.file_name,
                    "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
                    "summary": doc.analysis_summary,
                    "status": doc.status
                }
                for doc in docs
            ]
        }
        
    except Exception as e:
        logger.error(f"List documents error: {e}")
        return {"success": False, "error": str(e)}


@router.get("/{document_id}")
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_session)
):
    """Get detailed document analysis."""
    try:
        result = await db.execute(
            select(DocumentAnalysisDB).filter(DocumentAnalysisDB.id == document_id)
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "success": True,
            "document": {
                "id": doc.id,
                "document_type": doc.document_type,
                "file_name": doc.file_name,
                "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
                "ocr_text": doc.ocr_text,
                "summary": doc.analysis_summary,
                "extracted_data": doc.extracted_data,
                "confidence": doc.confidence_score,
                "status": doc.status
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document error: {e}")
        return {"success": False, "error": str(e)}


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_session)
):
    """Delete a document."""
    try:
        result = await db.execute(
            select(DocumentAnalysisDB).filter(DocumentAnalysisDB.id == document_id)
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        await db.delete(doc)
        await db.commit()
        
        return {"success": True, "message": "Document deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete document error: {e}")
        await db.rollback()
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# SECURE DOCUMENT PIPELINE — Privacy-First Architecture
# All endpoints below use UUID tracking + Presidio masking
# ═══════════════════════════════════════════════════════════════════


class SecureUploadRequest(BaseModel):
    """Secure upload with base64 image and user UUID."""
    image_data: str  # Base64 encoded
    user_uuid: str
    document_type: str = "auto"  # auto, finance, health, travel, shopping, legal, personal
    analyze: bool = True


class SecureTextRequest(BaseModel):
    """Secure text processing (no image)."""
    text: str
    user_uuid: str
    document_type: str = "auto"
    analyze: bool = True


class DocumentQueryRequest(BaseModel):
    """Ask a question about a processed document."""
    document_uuid: str
    question: str
    user_uuid: str


@router.post("/secure/upload", dependencies=[Depends(soft_rate_limit("documents"))])
async def secure_upload_image(request: SecureUploadRequest):
    """
    Privacy-first document upload pipeline.
    
    Flow: Image → OCR → Classify → Mask PII/PCI/HIPAA → UUID → Analyze
    
    - All sensitive entities are masked before LLM analysis
    - Original text is never stored raw (only SHA-256 hash)
    - Entity mappings stored locally, never sent externally
    - Returns document_uuid for future reference
    """
    from app.services.document_pipeline import get_document_pipeline

    try:
        # Decode base64
        if "," in request.image_data:
            image_bytes = base64.b64decode(request.image_data.split(",")[1])
        else:
            image_bytes = base64.b64decode(request.image_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large. Max 10MB.")

    pipeline = get_document_pipeline()
    result = await pipeline.process_image(
        image_data=image_bytes,
        user_uuid=request.user_uuid,
        document_type=request.document_type,
        analyze=request.analyze,
    )

    return result


@router.post("/secure/text")
async def secure_process_text(request: SecureTextRequest):
    """
    Privacy-first text processing (no image/OCR needed).
    
    Flow: Text → Classify → Mask PII/PCI/HIPAA → UUID → Analyze
    """
    from app.services.document_pipeline import get_document_pipeline

    if not request.text or len(request.text.strip()) < 5:
        raise HTTPException(status_code=400, detail="Text too short")

    pipeline = get_document_pipeline()
    result = await pipeline.process_text(
        text=request.text,
        user_uuid=request.user_uuid,
        document_type=request.document_type,
        analyze=request.analyze,
    )

    return result


@router.post("/secure/query")
async def secure_query_document(request: DocumentQueryRequest):
    """
    Ask a question about a previously processed document.
    Uses MASKED text only — original content never reaches the LLM.
    """
    from app.services.document_pipeline import get_document_pipeline

    pipeline = get_document_pipeline()
    result = await pipeline.query_document(
        document_uuid=request.document_uuid,
        question=request.question,
        user_uuid=request.user_uuid,
    )

    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Not found"))

    return result


@router.get("/secure/list/{user_uuid}")
async def secure_list_documents(user_uuid: str):
    """List all securely processed documents for a user."""
    from app.services.document_pipeline import get_document_pipeline

    pipeline = get_document_pipeline()
    docs = pipeline.get_user_documents(user_uuid)

    return {
        "success": True,
        "user_uuid": user_uuid,
        "count": len(docs),
        "documents": docs,
    }


@router.get("/secure/{document_uuid}")
async def secure_get_document(document_uuid: str, user_uuid: str):
    """Get a securely processed document by UUID."""
    from app.services.document_pipeline import get_document_pipeline

    pipeline = get_document_pipeline()
    doc = pipeline.get_document(document_uuid, user_uuid)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or access denied")

    return {"success": True, **doc}


@router.get("/privacy/check")
async def privacy_check(text: str):
    """Check if text contains sensitive data (without masking)."""
    from app.services.privacy_masking import get_masking_service

    service = get_masking_service()
    is_safe, detected = service.is_safe_for_llm(text)

    return {
        "is_safe": is_safe,
        "detected_entity_types": detected,
        "recommendation": "Safe to process" if is_safe else "Masking required before external processing",
    }


@router.get("/privacy/audit")
async def privacy_audit(limit: int = 50):
    """Get privacy audit log (masked prompt history)."""
    from app.services.llm_privacy_middleware import PrivateLLM

    return {
        "success": True,
        "stats": PrivateLLM.get_audit_stats(),
        "recent_entries": PrivateLLM.get_audit_log(limit),
    }
