---
name: pla-documents
description: Privacy-first document processing — OCR, classification, PII masking, and analysis via PLA backend.
metadata: { "openclaw": { "emoji": "🔒", "requires": { "bins": ["pla"] } } }
---

# Documents Skill (Privacy Pipeline)

Process documents through the privacy-first pipeline: OCR → classify → mask PII → UUID → analyze.
All sensitive data (SSN, credit cards, medical records, etc.) is masked BEFORE any LLM sees it.

## Commands

### Upload & analyze an image
```bash
pla doc-upload /path/to/photo.jpg           # Auto-classify + mask + analyze
pla health-upload /path/to/lab-results.jpg  # Force health classification
```

### Process text directly
```bash
pla doc-text "Account balance $5,234. SSN 123-45-6789. Patient John Smith."
```

### Query a processed document
```bash
pla doc-query doc-a1b2c3 "What was the total balance?"
pla doc-query doc-a1b2c3 "Are any lab values abnormal?"
```

### List & retrieve documents
```bash
pla doc-list                    # All your documents
pla doc-get doc-a1b2c3          # Details for one document
```

### Privacy checks
```bash
pla privacy-check "My SSN is 123-45-6789"   # Check if text has PII
pla privacy-audit                            # View masking audit log
```

## When the user shares a photo

1. Save the image to a temp file
2. Run `pla doc-upload <path>`
3. Report: document type, entity count masked, key findings
4. Save the document_uuid for follow-up questions

## Entity types detected

PII: PERSON, EMAIL, PHONE, ADDRESS, SSN, DRIVER_LICENSE, PASSPORT
PCI: CREDIT_CARD, BANK_ACCOUNT, ROUTING_NUMBER
HIPAA: HOSPITAL, MEDICAL_RECORD, HEALTH_PLAN_ID, NPI, DEA_NUMBER
SOX: ACCOUNT_NUMBER, API_KEY, PASSWORD
