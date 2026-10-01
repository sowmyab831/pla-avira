"""
Document Processing Pipeline — Privacy-First Architecture.

Camera Image / Upload
    → OCR extraction (Tesseract or LLaVA vision)
    → Document classification (finance/health/travel/shopping/legal/personal)
    → Sensitive entity detection (Presidio NER + regex)
    → Masking ([PERSON_001], [SSN_001], etc.)
    → UUID assignment
    → Store metadata locally
    → Send ONLY masked content to LLM for analysis
    → Return analysis with UUID reference

Original images stay encrypted. Raw text never leaves the server.
"""

import logging
import uuid
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime

from app.services.privacy_masking import get_masking_service
from app.services.document_ocr import get_ocr_service
from app.integrations.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

# In-memory store (replaced by DB in production via SecureDocumentDB + EntityMappingDB)
_document_store: Dict[str, Dict[str, Any]] = {}
_user_documents: Dict[str, list] = {}  # user_uuid → [document_uuids]


class DocumentPipeline:
    """
    End-to-end document processing with privacy masking.

    Usage:
        pipeline = DocumentPipeline()
        result = await pipeline.process_image(image_bytes, user_uuid="u-123")
        # result["document_uuid"] = "doc-abc..."
        # result["masked_text"] = "[PERSON_001] has balance..."
        # result["analysis"] = { ... }
    """

    def __init__(self):
        self.masking = get_masking_service()
        self.ocr = get_ocr_service()
        self.llm = OllamaClient(model="qwen2.5:7b")  # efficient model for analysis

    async def process_image(
        self,
        image_data: bytes,
        user_uuid: str,
        document_type: str = "auto",
        analyze: bool = True,
    ) -> Dict[str, Any]:
        """
        Full pipeline: image → OCR → classify → mask → UUID → analyze.

        Args:
            image_data: Raw image bytes from camera/upload
            user_uuid: User's UUID
            document_type: Override auto-classification
            analyze: Whether to run LLM analysis on masked text

        Returns:
            Document result with UUID, masked text, analysis, entity count
        """
        doc_uuid = f"doc-{uuid.uuid4().hex[:12]}"
        started = datetime.utcnow()

        try:
            # Step 1: OCR extraction
            logger.info(f"[{doc_uuid}] Step 1: OCR extraction")
            ocr_result = await self.ocr.analyze_image(image_data, document_type="auto")
            raw_text = ocr_result.get("ocr_text", "")

            if not raw_text or len(raw_text.strip()) < 10:
                return self._error_result(doc_uuid, user_uuid, "OCR failed — could not extract readable text")

            # Step 2: Classify document
            logger.info(f"[{doc_uuid}] Step 2: Classify document")
            if document_type == "auto":
                document_type = self.masking.classify_document(raw_text)
            logger.info(f"[{doc_uuid}] Classified as: {document_type}")

            # Step 3: Mask sensitive entities
            logger.info(f"[{doc_uuid}] Step 3: Mask sensitive entities")
            mask_result = self.masking.mask_text(
                text=raw_text,
                document_uuid=doc_uuid,
                user_uuid=user_uuid,
            )
            masked_text = mask_result["masked_text"]
            entity_count = mask_result["entity_count"]
            entity_mappings = mask_result["entity_mappings"]

            logger.info(f"[{doc_uuid}] Masked {entity_count} entities")

            # Step 4: Analyze masked text with LLM (if requested)
            analysis = {}
            if analyze and masked_text:
                logger.info(f"[{doc_uuid}] Step 4: LLM analysis on masked text")
                analysis = await self._analyze_masked_text(masked_text, document_type)

            # Step 5: Store document record
            raw_hash = hashlib.sha256(raw_text.encode()).hexdigest()
            elapsed = (datetime.utcnow() - started).total_seconds()

            document_record = {
                "document_uuid": doc_uuid,
                "user_uuid": user_uuid,
                "category": document_type,
                "masked_text": masked_text,
                "ocr_text_hash": raw_hash,
                "entity_count": entity_count,
                "entity_mappings": entity_mappings,
                "analysis": analysis,
                "confidence": ocr_result.get("confidence", 0.8),
                "status": "completed",
                "processing_time_seconds": round(elapsed, 2),
                "created_at": datetime.utcnow().isoformat(),
            }

            # Store in memory (production: write to SecureDocumentDB + EntityMappingDB)
            _document_store[doc_uuid] = document_record
            if user_uuid not in _user_documents:
                _user_documents[user_uuid] = []
            _user_documents[user_uuid].append(doc_uuid)

            logger.info(f"[{doc_uuid}] Pipeline complete in {elapsed:.1f}s")

            return {
                "success": True,
                "document_uuid": doc_uuid,
                "user_uuid": user_uuid,
                "category": document_type,
                "masked_text": masked_text,
                "entity_count": entity_count,
                "analysis": analysis,
                "processing_time_seconds": round(elapsed, 2),
            }

        except Exception as e:
            logger.error(f"[{doc_uuid}] Pipeline error: {e}")
            return self._error_result(doc_uuid, user_uuid, str(e))

    async def process_text(
        self,
        text: str,
        user_uuid: str,
        document_type: str = "auto",
        analyze: bool = True,
    ) -> Dict[str, Any]:
        """
        Process raw text (no OCR needed).
        Same pipeline minus OCR step.
        """
        doc_uuid = f"doc-{uuid.uuid4().hex[:12]}"
        started = datetime.utcnow()

        try:
            if document_type == "auto":
                document_type = self.masking.classify_document(text)

            mask_result = self.masking.mask_text(
                text=text,
                document_uuid=doc_uuid,
                user_uuid=user_uuid,
            )
            masked_text = mask_result["masked_text"]

            analysis = {}
            if analyze and masked_text:
                analysis = await self._analyze_masked_text(masked_text, document_type)

            raw_hash = hashlib.sha256(text.encode()).hexdigest()
            elapsed = (datetime.utcnow() - started).total_seconds()

            document_record = {
                "document_uuid": doc_uuid,
                "user_uuid": user_uuid,
                "category": document_type,
                "masked_text": masked_text,
                "ocr_text_hash": raw_hash,
                "entity_count": mask_result["entity_count"],
                "entity_mappings": mask_result["entity_mappings"],
                "analysis": analysis,
                "status": "completed",
                "processing_time_seconds": round(elapsed, 2),
                "created_at": datetime.utcnow().isoformat(),
            }

            _document_store[doc_uuid] = document_record
            if user_uuid not in _user_documents:
                _user_documents[user_uuid] = []
            _user_documents[user_uuid].append(doc_uuid)

            return {
                "success": True,
                "document_uuid": doc_uuid,
                "user_uuid": user_uuid,
                "category": document_type,
                "masked_text": masked_text,
                "entity_count": mask_result["entity_count"],
                "analysis": analysis,
                "processing_time_seconds": round(elapsed, 2),
            }

        except Exception as e:
            logger.error(f"[{doc_uuid}] Text pipeline error: {e}")
            return self._error_result(doc_uuid, user_uuid, str(e))

    async def query_document(
        self,
        document_uuid: str,
        question: str,
        user_uuid: str,
    ) -> Dict[str, Any]:
        """
        Ask a question about a previously processed document.
        Uses the MASKED version of the text — never raw.
        """
        doc = _document_store.get(document_uuid)
        if not doc:
            return {"success": False, "error": "Document not found"}

        if doc["user_uuid"] != user_uuid:
            return {"success": False, "error": "Access denied"}

        masked_text = doc["masked_text"]
        category = doc["category"]

        # Mask the question too (user might include sensitive data in question)
        q_mask = self.masking.mask_text(
            text=question,
            document_uuid=document_uuid,
            user_uuid=user_uuid,
        )

        prompt = f"""Based on this {category} document, answer the user's question.

DOCUMENT (masked for privacy):
{masked_text[:3000]}

USER QUESTION:
{q_mask["masked_text"]}

Provide a clear, helpful answer. If the document doesn't contain enough info, say so."""

        answer = await self.llm.generate(
            prompt,
            system="You are a helpful document analysis assistant. Respond concisely.",
            temperature=0.3,
        )

        return {
            "success": True,
            "document_uuid": document_uuid,
            "question": q_mask["masked_text"],
            "answer": answer,
            "category": category,
        }

    def get_document(self, document_uuid: str, user_uuid: str) -> Optional[Dict[str, Any]]:
        """Retrieve a document record by UUID."""
        doc = _document_store.get(document_uuid)
        if doc and doc["user_uuid"] == user_uuid:
            # Return without entity mappings (those are internal)
            return {k: v for k, v in doc.items() if k != "entity_mappings"}
        return None

    def get_user_documents(self, user_uuid: str) -> list:
        """List all documents for a user."""
        doc_uuids = _user_documents.get(user_uuid, [])
        docs = []
        for duuid in doc_uuids:
            doc = _document_store.get(duuid)
            if doc:
                docs.append({
                    "document_uuid": duuid,
                    "category": doc["category"],
                    "entity_count": doc["entity_count"],
                    "status": doc["status"],
                    "created_at": doc["created_at"],
                })
        return docs

    async def _analyze_masked_text(self, masked_text: str, doc_type: str) -> Dict[str, Any]:
        """Analyze masked text using local LLM."""
        prompts = {
            "finance": "Analyze this financial document. Extract: account summary, key transactions, balances, fees, and any action items. Note: personal identifiers have been masked for privacy.",
            "health": "Analyze this health/medical document. Extract: test results with values and ranges, abnormal findings, diagnoses, and recommendations. Note: personal identifiers have been masked for privacy.",
            "travel": "Analyze this travel document. Extract: itinerary details, booking references, dates, and costs. Note: personal identifiers have been masked for privacy.",
            "shopping": "Analyze this receipt/shopping document. Extract: items purchased, prices, totals, payment method, and any applicable returns. Note: personal identifiers have been masked for privacy.",
            "legal": "Analyze this legal document. Extract: key terms, parties involved, obligations, dates, and important clauses. Note: personal identifiers have been masked for privacy.",
            "personal": "Analyze this personal document. Extract: key information, dates, and any action items. Note: personal identifiers have been masked for privacy.",
        }

        system_prompt = "You are a document analysis assistant. Respond in JSON format with keys: summary, key_findings, action_items, extracted_data."
        prompt = prompts.get(doc_type, prompts["personal"]) + f"\n\nDOCUMENT:\n{masked_text[:3000]}"

        try:
            response = await self.llm.generate(
                prompt,
                system=system_prompt,
                temperature=0.2,
                json_mode=True,
            )

            import json
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {"summary": response[:500], "raw": True}

        except Exception as e:
            logger.error(f"LLM analysis error: {e}")
            return {"summary": f"Analysis pending — {doc_type} document", "error": str(e)}

    def _error_result(self, doc_uuid: str, user_uuid: str, error: str) -> Dict[str, Any]:
        return {
            "success": False,
            "document_uuid": doc_uuid,
            "user_uuid": user_uuid,
            "error": error,
        }


# Singleton
_pipeline: Optional[DocumentPipeline] = None


def get_document_pipeline() -> DocumentPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = DocumentPipeline()
    return _pipeline
