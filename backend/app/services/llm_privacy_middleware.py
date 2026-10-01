"""
LLM Privacy Middleware — Intercepts ALL prompts before sending to any LLM.

This is the last line of defense. Every prompt that goes to Ollama (or any
external LLM in the future) passes through this middleware.

Actions:
1. Scan prompt for sensitive data
2. If found → mask before sending
3. Log the masked prompt (audit trail)
4. Send masked prompt to LLM
5. Return response (no unmasking needed — LLM only sees masked tokens)

This middleware wraps OllamaClient and is the ONLY way to call LLMs
in the privacy-first architecture.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from app.integrations.ollama_client import OllamaClient
from app.services.privacy_masking import get_masking_service

logger = logging.getLogger(__name__)

# Audit log (in production: write to DB or secure file)
_audit_log: list = []
MAX_AUDIT_LOG = 1000


class PrivateLLM:
    """
    Privacy-safe LLM wrapper. Use this instead of OllamaClient directly
    when processing user content that may contain sensitive data.

    Usage:
        llm = PrivateLLM(user_uuid="u-123")
        response = await llm.generate("Analyze John Smith's SSN 123-45-6789 statement")
        # Prompt sent to Ollama: "Analyze [PERSON_001]'s SSN [SSN_001] statement"
    """

    def __init__(
        self,
        user_uuid: str = "anonymous",
        model: Optional[str] = None,
        role: Optional[str] = None,
    ):
        self.user_uuid = user_uuid
        self.masking = get_masking_service()

        if role:
            self.client = OllamaClient.for_role(role)
        elif model:
            self.client = OllamaClient(model=model)
        else:
            self.client = OllamaClient()

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        document_uuid: Optional[str] = None,
        skip_masking: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate with automatic privacy masking.

        Returns:
            {
                "response": "LLM response text",
                "was_masked": bool,
                "entities_masked": int,
                "audit_id": str,
            }
        """
        doc_uuid = document_uuid or f"prompt-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        # Step 1: Check if masking needed
        masked_prompt = prompt
        entities_masked = 0
        was_masked = False

        if not skip_masking:
            is_safe, detected = self.masking.is_safe_for_llm(prompt)

            if not is_safe:
                mask_result = self.masking.mask_text(
                    text=prompt,
                    document_uuid=doc_uuid,
                    user_uuid=self.user_uuid,
                )
                masked_prompt = mask_result["masked_text"]
                entities_masked = mask_result["entity_count"]
                was_masked = True
                logger.info(
                    f"Privacy middleware masked {entities_masked} entities "
                    f"in prompt for user {self.user_uuid}"
                )

        # Also mask system prompt if provided
        masked_system = system
        if system and not skip_masking:
            sys_safe, _ = self.masking.is_safe_for_llm(system)
            if not sys_safe:
                sys_result = self.masking.mask_text(
                    text=system,
                    document_uuid=doc_uuid,
                    user_uuid=self.user_uuid,
                )
                masked_system = sys_result["masked_text"]

        # Step 2: Audit log
        audit_id = f"audit-{len(_audit_log):06d}"
        audit_entry = {
            "audit_id": audit_id,
            "user_uuid": self.user_uuid,
            "document_uuid": doc_uuid,
            "was_masked": was_masked,
            "entities_masked": entities_masked,
            "prompt_length": len(prompt),
            "masked_prompt_length": len(masked_prompt),
            "model": self.client.model,
            "timestamp": datetime.utcnow().isoformat(),
        }
        _audit_log.append(audit_entry)
        if len(_audit_log) > MAX_AUDIT_LOG:
            _audit_log.pop(0)

        # Step 3: Send masked prompt to LLM
        response = await self.client.generate(
            prompt=masked_prompt,
            system=masked_system,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return {
            "response": response,
            "was_masked": was_masked,
            "entities_masked": entities_masked,
            "audit_id": audit_id,
        }

    async def chat(
        self,
        messages: list,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Chat with automatic privacy masking on all messages."""
        masked_messages = []
        total_masked = 0

        for msg in messages:
            content = msg.get("content", "")
            is_safe, _ = self.masking.is_safe_for_llm(content)

            if not is_safe:
                result = self.masking.mask_text(
                    text=content,
                    document_uuid=f"chat-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                    user_uuid=self.user_uuid,
                )
                masked_messages.append({
                    "role": msg["role"],
                    "content": result["masked_text"],
                })
                total_masked += result["entity_count"]
            else:
                masked_messages.append(msg)

        response = await self.client.chat(
            messages=masked_messages,
            temperature=temperature,
        )

        return {
            "response": response,
            "was_masked": total_masked > 0,
            "entities_masked": total_masked,
        }

    @staticmethod
    def get_audit_log(limit: int = 50) -> list:
        """Get recent audit entries."""
        return _audit_log[-limit:]

    @staticmethod
    def get_audit_stats() -> Dict[str, Any]:
        """Get audit statistics."""
        total = len(_audit_log)
        masked = sum(1 for e in _audit_log if e["was_masked"])
        total_entities = sum(e["entities_masked"] for e in _audit_log)

        return {
            "total_prompts": total,
            "masked_prompts": masked,
            "clean_prompts": total - masked,
            "total_entities_masked": total_entities,
            "masking_rate": f"{(masked / total * 100):.1f}%" if total > 0 else "0%",
        }
