"""Privacy module: PII/PHI/PCI detection and masking using Presidio."""
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

# Lazy initialization of Presidio engines
_analyzer = None
_anonymizer = None

def _get_analyzer():
    global _analyzer
    if _analyzer is None:
        try:
            from presidio_analyzer import AnalyzerEngine
            _analyzer = AnalyzerEngine()
        except Exception as e:
            logger.warning(f"Failed to initialize Presidio analyzer: {e}")
            _analyzer = False
    return _analyzer if _analyzer else None

def _get_anonymizer():
    global _anonymizer
    if _anonymizer is None:
        try:
            from presidio_anonymizer import AnonymizerEngine
            _anonymizer = AnonymizerEngine()
        except Exception as e:
            logger.warning(f"Failed to initialize Presidio anonymizer: {e}")
            _anonymizer = False
    return _anonymizer if _anonymizer else None

# Entities to detect (HIPAA/PCI/GDPR compliance)
SENSITIVE_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "US_SSN",
    "CREDIT_CARD",
    "IBAN_CODE",
    "US_BANK_ACCOUNT_NUMBER",
    "MEDICAL_LICENSE",
    "US_PASSPORT",
    "US_DRIVER_LICENSE",
    "DATE_TIME",  # For health records with dates
]


def mask_text(text: str, threshold: float = 0.5) -> Tuple[str, Dict]:
    """
    Detect and mask PII/PHI/PCI in text.
    
    Args:
        text: Input text to analyze
        threshold: Confidence threshold for entity detection (0.0-1.0)
    
    Returns:
        Tuple of (masked_text, pii_metadata)
        pii_metadata contains detected entities and their types
    """
    try:
        analyzer = _get_analyzer()
        if not analyzer:
            # If Presidio not available, return text as-is
            logger.warning("Presidio analyzer not available, skipping PII detection")
            return text, {"entities": [], "masked": False}
        
        # Analyze text for sensitive entities
        results = analyzer.analyze(
            text=text,
            entities=SENSITIVE_ENTITIES,
            language="en",
            score_threshold=threshold,
        )
        
        if not results:
            # No sensitive data detected
            return text, {"detected_entities": [], "is_masked": False}
        
        # Log detection for audit trail
        detected_types = [r.entity_type for r in results]
        logger.info(f"Detected entities: {detected_types}")
        
        # Anonymize detected entities
        anonymizer = _get_anonymizer()
        if not anonymizer:
            logger.warning("Presidio anonymizer not available, returning original text")
            return text, {"detected_entities": detected_types, "is_masked": False}
        
        from presidio_anonymizer.entities import OperatorConfig
        
        masked_text = anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators={
                "PERSON": OperatorConfig("replace", {"new_value": "[PERSON]"}),
                "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "[EMAIL]"}),
                "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[PHONE]"}),
                "US_SSN": OperatorConfig("replace", {"new_value": "[SSN]"}),
                "CREDIT_CARD": OperatorConfig("replace", {"new_value": "[CARD]"}),
                "IBAN_CODE": OperatorConfig("replace", {"new_value": "[IBAN]"}),
                "US_BANK_ACCOUNT_NUMBER": OperatorConfig("replace", {"new_value": "[ACCOUNT]"}),
                "MEDICAL_LICENSE": OperatorConfig("replace", {"new_value": "[LICENSE]"}),
                "US_PASSPORT": OperatorConfig("replace", {"new_value": "[PASSPORT]"}),
                "US_DRIVER_LICENSE": OperatorConfig("replace", {"new_value": "[LICENSE]"}),
                "DATE_TIME": OperatorConfig("replace", {"new_value": "[DATE]"}),
            },
        )
        
        pii_metadata = {
            "detected_entities": [
                {
                    "type": r.entity_type,
                    "score": r.score,
                    "start": r.start,
                    "end": r.end,
                }
                for r in results
            ],
            "is_masked": True,
        }
        
        return masked_text.text, pii_metadata
        
    except Exception as e:
        logger.error(f"Error in mask_text: {e}")
        # On error, return original text with error flag
        return text, {"detected_entities": [], "is_masked": False, "error": str(e)}


def audit_log_masking(user_id: str, original_length: int, masked_length: int, entities: List[str]):
    """
    Log masking operations for audit trail (HIPAA/GDPR compliance).
    
    In production, write to audit log database or external service.
    """
    logger.info(
        f"Masking audit: user={user_id}, original_len={original_length}, "
        f"masked_len={masked_length}, entities={entities}"
    )
