"""
Tests for the Privacy-First Document Pipeline.

Tests:
- PII/PCI/HIPAA entity detection
- Text masking (SSN, credit cards, emails, phones, names)
- Document classification
- UUID tracking
- LLM privacy middleware
"""

import pytest
from app.services.privacy_masking import PrivacyMaskingService


class TestPrivacyMasking:
    """Test the Presidio + regex masking service."""

    def setup_method(self):
        self.service = PrivacyMaskingService()

    def test_mask_ssn(self):
        """SSN should be detected and masked."""
        text = "My SSN is 123-45-6789 and I need help."
        result = self.service.mask_text(text, "doc-001", "user-001")

        assert "[SSN_" in result["masked_text"] or "[US_SSN_" in result["masked_text"]
        assert "123-45-6789" not in result["masked_text"]
        assert result["entity_count"] >= 1

    def test_mask_credit_card(self):
        """Credit card numbers should be masked."""
        text = "Pay with card 4111-1111-1111-1111 please."
        result = self.service.mask_text(text, "doc-002", "user-001")

        assert "4111-1111-1111-1111" not in result["masked_text"]
        assert result["entity_count"] >= 1

    def test_mask_email(self):
        """Email addresses should be masked."""
        text = "Contact me at john.smith@example.com for details."
        result = self.service.mask_text(text, "doc-003", "user-001")

        assert "john.smith@example.com" not in result["masked_text"]
        assert result["entity_count"] >= 1

    def test_mask_phone(self):
        """Phone numbers should be masked."""
        text = "Call me at (555) 123-4567 anytime."
        result = self.service.mask_text(text, "doc-004", "user-001")

        assert "(555) 123-4567" not in result["masked_text"]
        assert result["entity_count"] >= 1

    def test_mask_multiple_entities(self):
        """Multiple entity types in one text."""
        text = (
            "John Smith SSN 123-45-6789 has a medical bill from Duke Hospital. "
            "Email: john@duke.com, Phone: 555-123-4567."
        )
        result = self.service.mask_text(text, "doc-005", "user-001")

        assert "123-45-6789" not in result["masked_text"]
        assert "john@duke.com" not in result["masked_text"]
        assert result["entity_count"] >= 3
        assert len(result["entity_mappings"]) >= 3

    def test_entity_mappings_have_required_fields(self):
        """Entity mappings should have all required fields."""
        text = "SSN is 123-45-6789"
        result = self.service.mask_text(text, "doc-006", "user-001")

        if result["entity_mappings"]:
            mapping = result["entity_mappings"][0]
            assert "document_uuid" in mapping
            assert "user_uuid" in mapping
            assert "token" in mapping
            assert "entity_type" in mapping
            assert "original_hash" in mapping
            assert "partial_reveal" in mapping
            assert mapping["document_uuid"] == "doc-006"
            assert mapping["user_uuid"] == "user-001"

    def test_clean_text_passes_through(self):
        """Text without sensitive data should pass through unchanged."""
        text = "The weather is nice today in Charlotte."
        result = self.service.mask_text(text, "doc-007", "user-001")

        assert result["entity_count"] == 0
        assert result["masked_text"] == text

    def test_is_safe_for_llm(self):
        """Safety check should detect sensitive data."""
        safe, detected = self.service.is_safe_for_llm("The weather is nice.")
        assert safe is True
        assert len(detected) == 0

        safe, detected = self.service.is_safe_for_llm("My SSN is 123-45-6789")
        assert safe is False
        assert len(detected) > 0


class TestDocumentClassification:
    """Test document type classification."""

    def setup_method(self):
        self.service = PrivacyMaskingService()

    def test_classify_finance(self):
        """Finance documents should be classified correctly."""
        text = "Account balance: $5,234.00. Transaction on 01/15: Deposit $2,000. Interest earned: $12.50."
        assert self.service.classify_document(text) == "finance"

    def test_classify_health(self):
        """Health documents should be classified correctly."""
        text = "Patient diagnosis: Type 2 Diabetes. Blood glucose: 180 mg/dL. Hemoglobin A1c: 7.2%."
        assert self.service.classify_document(text) == "health"

    def test_classify_travel(self):
        """Travel documents should be classified correctly."""
        text = "Flight AA123 departing JFK. Hotel reservation at Marriott. Boarding pass for departure at 10am."
        assert self.service.classify_document(text) == "travel"

    def test_classify_shopping(self):
        """Shopping receipts should be classified correctly."""
        text = "Receipt #12345. Item: Widget x2, Qty: 2, Subtotal: $29.98. Tax: $2.40. Total: $32.38."
        assert self.service.classify_document(text) == "shopping"

    def test_classify_unknown(self):
        """Short/ambiguous text should return 'other'."""
        text = "Hello world."
        assert self.service.classify_document(text) == "other"


class TestPartialReveal:
    """Test partial reveal generation."""

    def setup_method(self):
        self.service = PrivacyMaskingService()

    def test_ssn_partial(self):
        partial = self.service._create_partial_reveal("123-45-6789", "US_SSN")
        assert partial == "***-**-6789"

    def test_card_partial(self):
        partial = self.service._create_partial_reveal("4111111111111111", "CREDIT_CARD")
        assert partial == "****1111"

    def test_email_partial(self):
        partial = self.service._create_partial_reveal("john@example.com", "EMAIL_ADDRESS")
        assert partial == "jo***@example.com"

    def test_person_partial(self):
        partial = self.service._create_partial_reveal("John Smith", "PERSON")
        assert "J***" in partial


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
