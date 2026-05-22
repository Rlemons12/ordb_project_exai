from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from app.models.configuration import get_exai_logger
from app.models.service.ai.base_ai_provider import (
    AIProviderError,
    AIProviderResponse,
    BaseAIProvider,
)


logger = get_exai_logger(__name__)


class OpenAIAIProvider(BaseAIProvider):
    """
    OpenAI implementation of the AI provider interface.

    This class intentionally only generates text. It does not know anything
    about Oracle. The orchestrator owns the database workflow.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        load_dotenv(override=False)

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.5")

        if not self.api_key:
            logger.error(
                "OPENAI_API_KEY is missing. Add it to your .env file."
            )
            raise AIProviderError(
                "OPENAI_API_KEY is missing. Add it to your .env file."
            )

        self.client = OpenAI(api_key=self.api_key)

        logger.info(
            "OpenAIAIProvider initialized. model=%s api_key_present=%s",
            self.model,
            bool(self.api_key),
        )

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> AIProviderResponse:
        """
        Generate text using the OpenAI Responses API.

        Args:
            system_prompt:
                High-level behavior/instruction prompt.

            user_prompt:
                User/task prompt.

        Returns:
            AIProviderResponse
        """
        logger.info(
            "OpenAI text generation requested. model=%s system_prompt_len=%s user_prompt_len=%s",
            self.model,
            len(system_prompt or ""),
            len(user_prompt or ""),
        )

        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
            )

            text = getattr(response, "output_text", None)

            if text is None:
                logger.debug(
                    "OpenAI response did not contain output_text. Trying fallback extraction."
                )
                text = self._fallback_extract_text(response)

            clean_text = text.strip() if text else ""

            logger.info(
                "OpenAI text generation completed. model=%s output_len=%s",
                self.model,
                len(clean_text),
            )

            return AIProviderResponse(
                success=True,
                text=clean_text,
                raw_response=response,
                error=None,
            )

        except Exception as exc:
            logger.exception("OpenAI text generation failed.")

            return AIProviderResponse(
                success=False,
                text="",
                raw_response=None,
                error=str(exc),
            )

    def _fallback_extract_text(self, response: Any) -> str:
        """
        Best-effort text extraction if output_text is not available.
        """
        try:
            parts: list[str] = []

            for item in getattr(response, "output", []) or []:
                for content in getattr(item, "content", []) or []:
                    text = getattr(content, "text", None)
                    if text:
                        parts.append(text)

            extracted_text = "\n".join(parts)

            logger.debug(
                "Fallback OpenAI response extraction completed. output_len=%s",
                len(extracted_text),
            )

            return extracted_text

        except Exception:
            logger.exception("Failed fallback response text extraction.")
            return ""