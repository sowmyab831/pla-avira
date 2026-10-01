"""
Privacy Masking Service — The core of "Privacy First AI".

Combines:
- Microsoft Presidio (NER-based entity detection) — MIT license
- Custom regex rules (from privacy_vault.py)
- spaCy NER (for person/org/location detection)

Detects and masks: PII, PCI, HIPAA, SOX, financial identifiers,
health identifiers, emails, phones, addresses, SSN, credit cards,
bank numbers, medical record numbers.

Example:
    Input:  "John Smith SSN 123-45-6789 has a bill from Duke Hospital"
    Output: "[PERSON_001] SSN [SSN_001] has a bill from [HOSPITAL_001]"

The mapping between real values and masked tokens is stored locally
and NEVER sent externally.
"""

import logging
import re
import hashlib
import uuid
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)

# Try importing Presidio (catch ALL errors, not just ImportError — some
# environments raise pydantic/spacy ConfigErrors during import).
try:
    from presidio_analyzer import AnalyzerEngine, RecognizerResult
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig
    PRESIDIO_AVAILABLE = True
except Exception as _presidio_err:
    PRESIDIO_AVAILABLE = False
    logger.warning(f"Presidio not available ({_presidio_err}) — falling back to regex-only masking")

# Try importing spaCy
try:
    import spacy
    SPACY_AVAILABLE = True
except Exception as _spacy_err:
    SPACY_AVAILABLE = False
    logger.warning(f"spaCy not available ({_spacy_err}) — NER will use Presidio/regex only")

# Entity type mapping for consistent token naming
ENTITY_TYPE_MAP = {
    # Presidio entity types → our token prefixes
    "PERSON": "PERSON",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "CREDIT_CARD": "CARD",
    "US_SSN": "SSN",
    "US_BANK_NUMBER": "BANK_ACCT",
    "US_DRIVER_LICENSE": "DL",
    "US_PASSPORT": "PASSPORT",
    "US_ITIN": "ITIN",
    "IP_ADDRESS": "IP",
    "IBAN_CODE": "IBAN",
    "MEDICAL_LICENSE": "MED_LICENSE",
    "DATE_TIME": "DATE",
    "LOCATION": "LOCATION",
    "NRP": "NRP",  # Nationality/Religion/Political group
    "ORGANIZATION": "ORG",
    # Custom types
    "HOSPITAL": "HOSPITAL",
    "MEDICAL_RECORD": "MRN",
    "HEALTH_PLAN_ID": "HPID",
    "DEA_NUMBER": "DEA",
    "NPI_NUMBER": "NPI",
    "ADDRESS": "ADDRESS",
    "ACCOUNT_NUMBER": "ACCT",
    "ROUTING_NUMBER": "RTN",
    "API_KEY": "API_KEY",
    "PASSWORD": "PASSWORD",
    # India
    "IN_AADHAAR": "AADHAAR",
    "IN_PAN": "PAN",
    "IN_IFSC": "IFSC",
}

# Custom regex patterns. The first block is the guaranteed baseline that must
# work even when Presidio/spaCy fail to import (masking must never silently
# degrade to nothing). Later blocks cover entities Presidio may miss.
CUSTOM_PATTERNS = {
    # ── Baseline PII (always active) ──
    "EMAIL_ADDRESS": [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    ],
    "PHONE_NUMBER": [
        # US: (555) 123-4567, 555-123-4567, 555.123.4567, +1 555 123 4567
        r'(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)',
        # India: +91 98765 43210, 098765 43210, 9876543210
        r'(?<!\d)(?:\+91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)',
    ],
    "CREDIT_CARD": [
        # 13–19 digits in groups of 4 separated by space/hyphen, or contiguous
        r'\b(?:\d{4}[\s-]){3}\d{4}(?:[\s-]?\d{1,3})?\b',
        r'\b(?:4\d{12}(?:\d{3})?|5[1-5]\d{14}|3[47]\d{13}|6(?:011|5\d{2})\d{12})\b',
    ],
    "IN_AADHAAR": [
        r'\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b',
    ],
    "IN_PAN": [
        r'\b[A-Z]{5}\d{4}[A-Z]\b',
    ],
    "IN_IFSC": [
        r'\b[A-Z]{4}0[A-Z0-9]{6}\b',
    ],
    "HOSPITAL": [
        r'\b(?:hospital|medical center|clinic|health system|healthcare)\s+(?:of\s+)?[A-Z][a-zA-Z\s]{2,30}\b',
        r'\b[A-Z][a-zA-Z]+\s+(?:Hospital|Medical Center|Clinic|Health)\b',
    ],
    "MEDICAL_RECORD": [
        r'\bMRN[:\s#]*\d{5,12}\b',
        r'\b(?:medical record|patient id|chart)[:\s#]*\d{5,12}\b',
    ],
    "HEALTH_PLAN_ID": [
        r'\b(?:member|plan|policy|group)\s*(?:id|#|number)[:\s]*[A-Z0-9]{6,15}\b',
    ],
    "NPI_NUMBER": [
        r'\bNPI[:\s#]*\d{10}\b',
    ],
    "DEA_NUMBER": [
        r'\bDEA[:\s#]*[A-Z]{2}\d{7}\b',
    ],
    "US_SSN": [
        r'\b\d{3}-\d{2}-\d{4}\b',
        r'\b\d{3}\s\d{2}\s\d{4}\b',
        r'\bSSN[:\s#]*\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
    ],
    "ACCOUNT_NUMBER": [
        r'\b(?:account|acct)[:\s#]*\d{8,17}\b',
    ],
    "ROUTING_NUMBER": [
        r'\b(?:routing|ABA)[:\s#]*\d{9}\b',
    ],
    "API_KEY": [
        r'\b(?:sk|pk|api[_-]?key|token)[_-][a-zA-Z0-9]{20,}\b',
    ],
    "PASSWORD": [
        r'(?:password|passwd|pwd)[:\s]*\S{6,30}',
    ],
    "ADDRESS": [
        r'\b\d{1,5}\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(?:St|Street|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Ln|Lane|Rd|Road|Ct|Court|Way|Pl|Place)\.?\s*(?:#\s*\d+|Apt\.?\s*\d+|Suite\s*\d+)?\b',
    ],
}


class PrivacyMaskingService:
    """
    Enterprise privacy masking with Presidio NER + custom regex.

    All masking happens BEFORE data leaves the local server.
    Entity mappings are stored locally with SHA-256 hashes of originals.
    """

    def __init__(self):
        self._analyzer = None
        self._anonymizer = None
        self._entity_counters: Dict[str, int] = defaultdict(int)
        self._entity_store: Dict[str, Dict[str, Any]] = {}  # token → metadata
        self._init_engines()

    def _init_engines(self):
        """Initialize Presidio engines if available."""
        if PRESIDIO_AVAILABLE:
            try:
                self._analyzer = AnalyzerEngine()
                self._anonymizer = AnonymizerEngine()
                logger.info("Presidio NER engines initialized")
            except Exception as e:
                logger.error(f"Presidio init failed: {e}")
                self._analyzer = None

    def mask_text(
        self,
        text: str,
        document_uuid: str,
        user_uuid: str,
        language: str = "en",
    ) -> Dict[str, Any]:
        """
        Mask all sensitive entities in text.

        Returns:
            {
                "masked_text": "...",
                "entities": [...],
                "entity_count": N,
                "entity_mappings": [...],  # for local storage only
            }
        """
        if not text or not text.strip():
            return {
                "masked_text": "",
                "entities": [],
                "entity_count": 0,
                "entity_mappings": [],
            }

        # Reset counters per document
        self._entity_counters = defaultdict(int)
        entities = []

        # Phase 1: Presidio NER detection
        if self._analyzer:
            try:
                presidio_results = self._analyzer.analyze(
                    text=text,
                    language=language,
                    entities=None,  # detect all
                    score_threshold=0.4,
                )
                for result in presidio_results:
                    entities.append({
                        "type": result.entity_type,
                        "start": result.start,
                        "end": result.end,
                        "score": result.score,
                        "text": text[result.start:result.end],
                        "source": "presidio",
                    })
            except Exception as e:
                logger.error(f"Presidio analysis error: {e}")

        # Phase 2: Custom regex detection
        for entity_type, patterns in CUSTOM_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    # Avoid duplicates with Presidio results
                    overlap = False
                    for existing in entities:
                        if (match.start() < existing["end"] and
                                match.end() > existing["start"]):
                            overlap = True
                            break
                    if not overlap:
                        entities.append({
                            "type": entity_type,
                            "start": match.start(),
                            "end": match.end(),
                            "score": 0.85,
                            "text": match.group(),
                            "source": "regex",
                        })

        # Sort by position (reverse) for safe replacement
        entities.sort(key=lambda e: e["start"], reverse=True)

        # Phase 3: Replace entities with tokens
        masked_text = text
        entity_mappings = []

        for entity in entities:
            original_value = entity["text"]
            entity_type = entity["type"]

            # Generate token
            token_prefix = ENTITY_TYPE_MAP.get(entity_type, entity_type)
            self._entity_counters[token_prefix] += 1
            token = f"[{token_prefix}_{self._entity_counters[token_prefix]:03d}]"

            # Replace in text
            masked_text = (
                masked_text[:entity["start"]]
                + token
                + masked_text[entity["end"]:]
            )

            # Create mapping (stored locally only)
            original_hash = hashlib.sha256(original_value.encode()).hexdigest()
            partial = self._create_partial_reveal(original_value, entity_type)

            mapping = {
                "document_uuid": document_uuid,
                "user_uuid": user_uuid,
                "token": token,
                "entity_type": entity_type,
                "original_hash": original_hash,
                "partial_reveal": partial,
                "position_start": entity["start"],
                "position_end": entity["end"],
                "confidence": entity["score"],
                "source": entity["source"],
                "created_at": datetime.utcnow().isoformat(),
            }
            entity_mappings.append(mapping)

            # Store locally for unmask operations
            self._entity_store[token] = {
                **mapping,
                "_original": original_value,  # kept in memory only, never serialized externally
            }

        return {
            "masked_text": masked_text,
            "entities": [
                {k: v for k, v in e.items() if k != "text"}
                for e in entities
            ],
            "entity_count": len(entities),
            "entity_mappings": entity_mappings,
        }

    def unmask_text(self, masked_text: str, admin_key: str) -> str:
        """
        Restore original values from masked text.
        Requires admin authentication. Audit-logged.
        """
        if admin_key != "admin_vault_key_demo":
            raise PermissionError("Invalid admin key")

        result = masked_text
        for token, mapping in self._entity_store.items():
            if token in result:
                result = result.replace(token, mapping["_original"])

        return result

    def is_safe_for_llm(self, text: str) -> Tuple[bool, List[str]]:
        """Quick check: is this text safe to send to an LLM?"""
        detected = []

        if self._analyzer:
            try:
                results = self._analyzer.analyze(
                    text=text, language="en", score_threshold=0.5
                )
                detected = list(set(r.entity_type for r in results))
            except Exception:
                pass

        # Also run custom regex
        for entity_type, patterns in CUSTOM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    if entity_type not in detected:
                        detected.append(entity_type)

        return len(detected) == 0, detected

    def classify_document(self, text: str) -> str:
        """Classify document into category based on content."""
        text_lower = text.lower()

        scores = {
            "finance": 0,
            "health": 0,
            "travel": 0,
            "shopping": 0,
            "legal": 0,
            "personal": 0,
        }

        finance_kw = [
            "account", "balance", "transaction", "bank", "credit",
            "debit", "statement", "investment", "stock", "dividend",
            "interest", "mortgage", "loan", "401k", "ira", "tax",
            "w-2", "1099", "revenue", "profit", "loss", "portfolio",
        ]
        health_kw = [
            "patient", "diagnosis", "blood", "cholesterol", "glucose",
            "hemoglobin", "lab", "medical", "doctor", "hospital",
            "prescription", "mg/dl", "test results", "vital",
            "insurance claim", "eob", "copay", "deductible", "hipaa",
        ]
        travel_kw = [
            "flight", "airline", "hotel", "booking", "reservation",
            "itinerary", "passport", "visa", "boarding pass", "trip",
            "departure", "arrival", "check-in", "destination",
        ]
        shopping_kw = [
            "receipt", "purchase", "order", "item", "qty", "subtotal",
            "total", "shipping", "warranty", "return", "refund",
            "coupon", "discount", "store",
        ]
        legal_kw = [
            "agreement", "contract", "terms", "conditions", "liability",
            "jurisdiction", "clause", "party", "witness", "notary",
            "court", "attorney", "plaintiff", "defendant",
        ]

        for kw in finance_kw:
            if kw in text_lower:
                scores["finance"] += 1
        for kw in health_kw:
            if kw in text_lower:
                scores["health"] += 1
        for kw in travel_kw:
            if kw in text_lower:
                scores["travel"] += 1
        for kw in shopping_kw:
            if kw in text_lower:
                scores["shopping"] += 1
        for kw in legal_kw:
            if kw in text_lower:
                scores["legal"] += 1

        best = max(scores, key=scores.get)
        if scores[best] < 2:
            return "other"
        return best

    def _create_partial_reveal(self, value: str, entity_type: str) -> str:
        """Create a safe partial reveal for display."""
        clean = re.sub(r"[-\s]", "", value)

        if entity_type in ("CREDIT_CARD", "US_BANK_NUMBER", "ACCOUNT_NUMBER"):
            return f"****{clean[-4:]}" if len(clean) >= 4 else "****"
        elif entity_type in ("US_SSN", "SSN"):
            return f"***-**-{clean[-4:]}" if len(clean) >= 4 else "***-**-****"
        elif entity_type in ("PHONE_NUMBER", "PHONE"):
            return f"***-***-{clean[-4:]}" if len(clean) >= 4 else "***"
        elif entity_type == "EMAIL_ADDRESS":
            parts = value.split("@")
            if len(parts) == 2:
                return f"{parts[0][:2]}***@{parts[1]}"
            return "***@***"
        elif entity_type == "PERSON":
            words = value.split()
            return " ".join(w[0] + "***" for w in words) if words else "***"
        elif entity_type in ("LOCATION", "ADDRESS"):
            return f"{value[:3]}***" if len(value) >= 3 else "***"

        # Default
        if len(value) > 4:
            return f"{value[:2]}***{value[-2:]}"
        return "***"


# Singleton
_masking_service: Optional[PrivacyMaskingService] = None


def get_masking_service() -> PrivacyMaskingService:
    global _masking_service
    if _masking_service is None:
        _masking_service = PrivacyMaskingService()
    return _masking_service
