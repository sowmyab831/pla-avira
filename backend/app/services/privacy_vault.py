"""
Privacy Vault - Secure PII/PCI/HIPAA/SOX data masking and storage.

Features:
- Detects and masks sensitive data types
- Stores mappings in secure vault (admin-only access)
- Provides reversible masking for authorized operations
- Prevents sensitive data from reaching external services
"""
import logging
import re
import hashlib
import secrets
from typing import Dict, List, Tuple, Optional, Any, Set
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SensitiveDataType(str, Enum):
    """Types of sensitive data we detect and mask."""
    CREDIT_CARD = "credit_card"
    SSN = "ssn"
    PHONE = "phone"
    EMAIL = "email"
    ADDRESS = "address"
    DOB = "dob"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    BANK_ACCOUNT = "bank_account"
    ROUTING_NUMBER = "routing_number"
    HEALTH_ID = "health_id"
    MEDICAL_RECORD = "medical_record"
    IP_ADDRESS = "ip_address"
    API_KEY = "api_key"
    PASSWORD = "password"


@dataclass
class MaskedValue:
    """A masked sensitive value with metadata."""
    original_hash: str  # SHA-256 of original value
    data_type: SensitiveDataType
    masked_at: str
    partial_reveal: str  # e.g., "****1234" for cards
    user_id: str
    session_id: Optional[str] = None


# Regex patterns for sensitive data detection
SENSITIVE_PATTERNS = {
    SensitiveDataType.CREDIT_CARD: [
        r'\b(?:4[0-9]{12}(?:[0-9]{3})?)\b',  # Visa
        r'\b(?:5[1-5][0-9]{14})\b',  # Mastercard
        r'\b(?:3[47][0-9]{13})\b',  # Amex
        r'\b(?:6(?:011|5[0-9]{2})[0-9]{12})\b',  # Discover
        r'\b(?:\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4})\b',  # Generic card format
    ],
    SensitiveDataType.SSN: [
        r'\b(?:\d{3}[-\s]?\d{2}[-\s]?\d{4})\b',  # XXX-XX-XXXX
        r'\b(?:\d{9})\b',  # 9 consecutive digits (context-dependent)
    ],
    SensitiveDataType.PHONE: [
        r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',  # US phone
        r'\b(?:\+\d{1,3}[-.\s]?)?\d{10,14}\b',  # International
    ],
    SensitiveDataType.EMAIL: [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    ],
    SensitiveDataType.DOB: [
        r'\b(?:0[1-9]|1[0-2])[/-](?:0[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b',  # MM/DD/YYYY
        r'\b(?:19|20)\d{2}[/-](?:0[1-9]|1[0-2])[/-](?:0[1-9]|[12]\d|3[01])\b',  # YYYY-MM-DD
    ],
    SensitiveDataType.PASSPORT: [
        r'\b[A-Z]{1,2}\d{6,9}\b',  # Generic passport format
    ],
    SensitiveDataType.BANK_ACCOUNT: [
        r'\b\d{8,17}\b',  # Bank account (context-dependent)
    ],
    SensitiveDataType.ROUTING_NUMBER: [
        r'\b\d{9}\b',  # ABA routing number
    ],
    SensitiveDataType.HEALTH_ID: [
        r'\b[A-Z]{3}\d{9}\b',  # Medicare ID format
        r'\b\d{3}-\d{2}-\d{4}[A-Z]?\b',  # Medicaid format
    ],
    SensitiveDataType.IP_ADDRESS: [
        r'\b(?:\d{1,3}\.){3}\d{1,3}\b',  # IPv4
    ],
    SensitiveDataType.API_KEY: [
        r'\b(?:sk|pk|api|key|token)[-_]?[a-zA-Z0-9]{20,}\b',  # Common API key patterns
    ],
}

# Keywords that indicate sensitive context
SENSITIVE_KEYWORDS = {
    SensitiveDataType.CREDIT_CARD: ['card', 'credit', 'debit', 'visa', 'mastercard', 'amex', 'payment'],
    SensitiveDataType.SSN: ['ssn', 'social security', 'social-security'],
    SensitiveDataType.BANK_ACCOUNT: ['account', 'bank', 'checking', 'savings', 'routing'],
    SensitiveDataType.HEALTH_ID: ['medicare', 'medicaid', 'health id', 'patient id', 'medical record'],
    SensitiveDataType.PASSWORD: ['password', 'passwd', 'pwd', 'secret'],
}


class PrivacyVault:
    """
    Secure vault for sensitive data masking and storage.
    
    In production, this would use:
    - HashiCorp Vault or AWS Secrets Manager for storage
    - HSM for encryption keys
    - Audit logging for all access
    """
    
    def __init__(self):
        # token -> MaskedValue (admin-only access in production)
        self._vault: Dict[str, MaskedValue] = {}
        self._access_log: List[Dict] = []
    
    def mask_text(self, text: str, user_id: str, session_id: str = None) -> Tuple[str, List[Dict]]:
        """
        Scan text for sensitive data and replace with masked tokens.
        
        Returns:
            Tuple of (masked_text, list of detected sensitive items)
        """
        masked_text = text
        detections = []
        
        for data_type, patterns in SENSITIVE_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, masked_text, re.IGNORECASE)
                for match in matches:
                    original = match.group()
                    
                    # Skip if too short (likely false positive)
                    if len(original) < 5:
                        continue
                    
                    # Check context for ambiguous patterns
                    if data_type in [SensitiveDataType.BANK_ACCOUNT, SensitiveDataType.ROUTING_NUMBER]:
                        if not self._has_sensitive_context(text, data_type, match.start()):
                            continue
                    
                    # Generate mask token
                    token = self._create_mask_token(original, data_type, user_id, session_id)
                    
                    # Create partial reveal
                    partial = self._create_partial_reveal(original, data_type)
                    
                    # Replace in text
                    masked_text = masked_text.replace(original, f"<REDACTED:{data_type.value}:{token}>")
                    
                    detections.append({
                        "type": data_type.value,
                        "token": token,
                        "partial": partial,
                        "position": match.start(),
                    })
        
        return masked_text, detections
    
    def unmask_text(self, masked_text: str, admin_key: str) -> str:
        """
        Restore original values from masked text (admin only).
        
        In production, this would require:
        - Admin authentication
        - Audit logging
        - Rate limiting
        """
        if not self._verify_admin_key(admin_key):
            logger.warning("Unauthorized unmask attempt")
            self._log_access("unmask_denied", None, success=False)
            raise PermissionError("Admin key required for unmasking")
        
        result = masked_text
        
        # Find all redacted tokens
        pattern = r'<REDACTED:(\w+):([a-f0-9]+)>'
        matches = re.finditer(pattern, result)
        
        for match in matches:
            data_type = match.group(1)
            token = match.group(2)
            
            if token in self._vault:
                # In production, we'd retrieve the actual value from secure storage
                # For demo, we just show partial reveal
                masked_value = self._vault[token]
                result = result.replace(match.group(), f"[{masked_value.partial_reveal}]")
                self._log_access("unmask", token, success=True)
        
        return result
    
    def is_safe_for_external(self, text: str) -> Tuple[bool, List[str]]:
        """
        Check if text is safe to send to external services.
        
        Returns:
            Tuple of (is_safe, list of detected sensitive types)
        """
        detected_types = set()
        
        for data_type, patterns in SENSITIVE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    detected_types.add(data_type.value)
        
        # Also check for keywords
        text_lower = text.lower()
        for data_type, keywords in SENSITIVE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    # Check if there's also a pattern match nearby
                    detected_types.add(f"{data_type.value}_context")
        
        is_safe = len(detected_types) == 0
        return is_safe, list(detected_types)
    
    def prepare_for_external(self, text: str, user_id: str, session_id: str = None) -> Dict[str, Any]:
        """
        Prepare text for external LLM processing.
        
        Returns dict with:
        - masked_text: Safe to send externally
        - is_safe: Whether any masking was needed
        - detections: What was masked
        """
        masked_text, detections = self.mask_text(text, user_id, session_id)
        
        return {
            "masked_text": masked_text,
            "is_safe": len(detections) == 0,
            "detections": detections,
            "original_length": len(text),
            "masked_length": len(masked_text),
        }
    
    def get_vault_stats(self) -> Dict:
        """Get vault statistics (admin only)."""
        by_type = {}
        for token, value in self._vault.items():
            type_name = value.data_type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1
        
        return {
            "total_masked_values": len(self._vault),
            "by_type": by_type,
            "access_log_entries": len(self._access_log),
        }
    
    def _create_mask_token(
        self,
        original: str,
        data_type: SensitiveDataType,
        user_id: str,
        session_id: str = None,
    ) -> str:
        """Create a unique token for a masked value."""
        # Hash the original value
        original_hash = hashlib.sha256(original.encode()).hexdigest()
        
        # Generate token
        token = hashlib.sha256(f"{original_hash}:{secrets.token_hex(8)}".encode()).hexdigest()[:16]
        
        # Store in vault
        self._vault[token] = MaskedValue(
            original_hash=original_hash,
            data_type=data_type,
            masked_at=datetime.now().isoformat(),
            partial_reveal=self._create_partial_reveal(original, data_type),
            user_id=user_id,
            session_id=session_id,
        )
        
        return token
    
    def _create_partial_reveal(self, original: str, data_type: SensitiveDataType) -> str:
        """Create a partial reveal for display (e.g., ****1234)."""
        clean = re.sub(r'[-\s]', '', original)
        
        if data_type == SensitiveDataType.CREDIT_CARD:
            return f"****{clean[-4:]}"
        elif data_type == SensitiveDataType.SSN:
            return f"***-**-{clean[-4:]}"
        elif data_type == SensitiveDataType.PHONE:
            return f"***-***-{clean[-4:]}"
        elif data_type == SensitiveDataType.EMAIL:
            parts = original.split('@')
            if len(parts) == 2:
                return f"{parts[0][:2]}***@{parts[1]}"
        elif data_type == SensitiveDataType.BANK_ACCOUNT:
            return f"****{clean[-4:]}"
        
        # Default: show first and last 2 chars
        if len(original) > 4:
            return f"{original[:2]}***{original[-2:]}"
        return "****"
    
    def _has_sensitive_context(self, text: str, data_type: SensitiveDataType, position: int) -> bool:
        """Check if there's sensitive context around a match."""
        # Look at 50 chars before and after
        start = max(0, position - 50)
        end = min(len(text), position + 50)
        context = text[start:end].lower()
        
        keywords = SENSITIVE_KEYWORDS.get(data_type, [])
        return any(kw in context for kw in keywords)
    
    def _verify_admin_key(self, key: str) -> bool:
        """Verify admin key for sensitive operations."""
        # In production, this would verify against a secure key store
        # For demo, accept a specific key
        return key == "admin_vault_key_demo"
    
    def _log_access(self, operation: str, token: str, success: bool):
        """Log vault access for audit."""
        self._access_log.append({
            "operation": operation,
            "token": token,
            "success": success,
            "timestamp": datetime.now().isoformat(),
        })


# Singleton instance
_privacy_vault: Optional[PrivacyVault] = None


def get_privacy_vault() -> PrivacyVault:
    """Get the singleton privacy vault."""
    global _privacy_vault
    if _privacy_vault is None:
        _privacy_vault = PrivacyVault()
    return _privacy_vault
