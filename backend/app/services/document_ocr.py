"""
Document OCR and Analysis Service
Uses Tesseract (free, open-source) for OCR and local LLM for analysis
"""
import logging
import os
import base64
import tempfile
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
import re
import json

from app.services.llm_client import generate as llm_generate

logger = logging.getLogger(__name__)

# Try importing OCR libraries
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("Tesseract/PIL not available - OCR will use fallback")

try:
    import pdf2image
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False


class DocumentOCRService:
    """
    Enterprise document analysis service using free/open-source tools:
    - Tesseract OCR (free)
    - Local Ollama LLM for analysis (free)
    - Supports health reports, bank statements, receipts
    """
    
    def __init__(self):
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
        
    async def analyze_image(
        self,
        image_data: bytes,
        document_type: str = "auto",
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Analyze an image document (health report, bank statement, receipt, etc.)
        """
        try:
            # Extract text using OCR
            ocr_text = await self._extract_text_from_image(image_data)
            
            if not ocr_text or len(ocr_text.strip()) < 10:
                return {
                    "success": False,
                    "error": "Could not extract text from image. Please ensure the image is clear and contains readable text.",
                    "ocr_text": ocr_text
                }
            
            # Auto-detect document type if not specified
            if document_type == "auto":
                document_type = self._detect_document_type(ocr_text)
            
            # Analyze based on document type
            analysis = await self._analyze_document(ocr_text, document_type)
            
            return {
                "success": True,
                "document_type": document_type,
                "ocr_text": ocr_text,
                "analysis": analysis,
                "extracted_data": analysis.get("extracted_data", {}),
                "summary": analysis.get("summary", ""),
                "confidence": analysis.get("confidence", 0.8),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Document analysis error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def analyze_pdf(
        self,
        pdf_data: bytes,
        document_type: str = "auto",
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """Analyze a PDF document."""
        try:
            if not PDF2IMAGE_AVAILABLE:
                return {
                    "success": False,
                    "error": "PDF processing not available. Please upload an image instead."
                }
            
            # Convert PDF to images
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(pdf_data)
                f.flush()
                
                images = pdf2image.convert_from_path(f.name, first_page=1, last_page=5)
            
            os.unlink(f.name)
            
            # Extract text from all pages
            all_text = []
            for img in images:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as img_file:
                    img.save(img_file.name)
                    with open(img_file.name, "rb") as f:
                        img_data = f.read()
                    text = await self._extract_text_from_image(img_data)
                    all_text.append(text)
                    os.unlink(img_file.name)
            
            ocr_text = "\n\n--- Page Break ---\n\n".join(all_text)
            
            # Auto-detect and analyze
            if document_type == "auto":
                document_type = self._detect_document_type(ocr_text)
            
            analysis = await self._analyze_document(ocr_text, document_type)
            
            return {
                "success": True,
                "document_type": document_type,
                "pages_processed": len(images),
                "ocr_text": ocr_text,
                "analysis": analysis,
                "extracted_data": analysis.get("extracted_data", {}),
                "summary": analysis.get("summary", ""),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"PDF analysis error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _extract_text_from_image(self, image_data: bytes) -> str:
        """Extract text from image using Tesseract OCR."""
        if not TESSERACT_AVAILABLE:
            # Fallback: try using Ollama vision if available
            return await self._extract_text_with_llm(image_data)
        
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(image_data)
                f.flush()
                
                img = Image.open(f.name)
                # Enhance image for better OCR
                img = img.convert('L')  # Grayscale
                
                # Run Tesseract
                text = pytesseract.image_to_string(img, config='--psm 6')
                
                os.unlink(f.name)
                return text.strip()
                
        except Exception as e:
            logger.error(f"Tesseract OCR error: {e}")
            return await self._extract_text_with_llm(image_data)
    
    async def _extract_text_with_llm(self, image_data: bytes) -> str:
        """Fallback: Use LLM vision to extract text."""
        try:
            # Encode image as base64
            b64_image = base64.b64encode(image_data).decode('utf-8')
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.ollama_host}/api/generate",
                    json={
                        "model": "llava:7b",  # Vision model
                        "prompt": "Extract ALL text from this image. Return only the extracted text, nothing else.",
                        "images": [b64_image],
                        "stream": False
                    }
                )
                
                if response.status_code == 200:
                    return response.json().get("response", "")
                    
        except Exception as e:
            logger.error(f"LLM vision OCR error: {e}")
        
        return ""
    
    def _detect_document_type(self, text: str) -> str:
        """Auto-detect document type from OCR text."""
        text_lower = text.lower()
        
        # Health report indicators
        health_keywords = ["patient", "diagnosis", "blood", "cholesterol", "hemoglobin", 
                         "glucose", "lab results", "medical", "doctor", "hospital",
                         "prescription", "mg/dl", "normal range", "test results"]
        
        # Bank/Finance indicators
        finance_keywords = ["account", "balance", "transaction", "deposit", "withdrawal",
                          "statement", "bank", "credit", "debit", "interest", "apr",
                          "routing", "checking", "savings", "investment"]
        
        # Receipt indicators
        receipt_keywords = ["receipt", "total", "subtotal", "tax", "payment", "visa",
                          "mastercard", "change", "qty", "item", "price"]
        
        health_score = sum(1 for k in health_keywords if k in text_lower)
        finance_score = sum(1 for k in finance_keywords if k in text_lower)
        receipt_score = sum(1 for k in receipt_keywords if k in text_lower)
        
        scores = {"health": health_score, "finance": finance_score, "receipt": receipt_score}
        detected = max(scores, key=scores.get)
        
        if scores[detected] < 2:
            return "general"
        
        return detected
    
    async def _analyze_document(self, text: str, doc_type: str) -> Dict[str, Any]:
        """Analyze document using local LLM."""
        prompts = {
            "health": """Analyze this health report/lab results. Extract:
1. Patient information (name, date, ID if available)
2. Test results with values and reference ranges
3. Any abnormal values (flag them)
4. Key findings or diagnoses
5. Recommendations if any

Format as JSON with keys: patient_info, test_results, abnormal_values, findings, recommendations

Text:
""",
            "finance": """Analyze this bank statement/financial document. Extract:
1. Account information (type, number - last 4 digits only)
2. Statement period
3. Opening and closing balance
4. Total deposits and withdrawals
5. Key transactions
6. Any fees or charges

Format as JSON with keys: account_info, period, balances, transactions_summary, fees

Text:
""",
            "receipt": """Analyze this receipt. Extract:
1. Store/Vendor name
2. Date and time
3. Items purchased with prices
4. Subtotal, tax, total
5. Payment method
6. Any discounts applied

Format as JSON with keys: vendor, date, items, subtotal, tax, total, payment_method, discounts

Text:
""",
            "general": """Analyze this document and extract key information:
1. Document type/purpose
2. Key dates mentioned
3. Important names/entities
4. Main content summary
5. Action items if any

Format as JSON with keys: type, dates, entities, summary, action_items

Text:
"""
        }
        
        prompt = prompts.get(doc_type, prompts["general"]) + text[:4000]
        
        try:
            result = await llm_generate(
                prompt, task="fast", temperature=0.3, timeout=60, json_mode=True,
            )

            if result:
                # Try to parse JSON from response
                extracted_data = self._parse_json_from_response(result)

                # Generate summary
                summary = await self._generate_summary(text, doc_type)

                return {
                    "extracted_data": extracted_data,
                    "raw_analysis": result,
                    "summary": summary,
                    "confidence": 0.85 if extracted_data else 0.6
                }

        except Exception as e:
            logger.error(f"LLM analysis error: {e}")
        
        # Fallback: basic extraction
        return {
            "extracted_data": self._basic_extraction(text, doc_type),
            "summary": f"Document type: {doc_type}. Contains {len(text)} characters of text.",
            "confidence": 0.5
        }
    
    def _parse_json_from_response(self, response: str) -> Dict[str, Any]:
        """Extract JSON from LLM response."""
        try:
            # Try to find JSON block
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        return {}
    
    def _basic_extraction(self, text: str, doc_type: str) -> Dict[str, Any]:
        """Basic regex-based extraction as fallback."""
        data = {}
        
        # Extract dates
        dates = re.findall(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text)
        if dates:
            data["dates"] = dates[:5]
        
        # Extract currency amounts
        amounts = re.findall(r'\$[\d,]+\.?\d*', text)
        if amounts:
            data["amounts"] = amounts[:10]
        
        # Extract percentages
        percentages = re.findall(r'\d+\.?\d*\s*%', text)
        if percentages:
            data["percentages"] = percentages[:5]
        
        if doc_type == "health":
            # Look for common lab values
            glucose = re.search(r'glucose[:\s]*(\d+)', text, re.I)
            if glucose:
                data["glucose"] = glucose.group(1)
            
            cholesterol = re.search(r'cholesterol[:\s]*(\d+)', text, re.I)
            if cholesterol:
                data["cholesterol"] = cholesterol.group(1)
        
        return data
    
    async def _generate_summary(self, text: str, doc_type: str) -> str:
        """Generate a brief summary."""
        try:
            prompt = f"Summarize this {doc_type} document in 2-3 sentences:\n\n{text[:2000]}"

            result = await llm_generate(
                prompt, task="fast", temperature=0.3, max_tokens=150, timeout=30,
            )
            if result:
                return result[:500]

        except Exception as e:
            logger.error(f"Summary generation error: {e}")

        return f"This appears to be a {doc_type} document."


# Singleton
_ocr_service: Optional[DocumentOCRService] = None

def get_ocr_service() -> DocumentOCRService:
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = DocumentOCRService()
    return _ocr_service
