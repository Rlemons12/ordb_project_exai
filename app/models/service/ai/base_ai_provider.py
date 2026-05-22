from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.models.configuration import get_exai_logger


logger = get_exai_logger(__name__)


class AIProviderError(RuntimeError):
    """
    Raised when an AI provider fails.
    """


@dataclass
class AIProviderResponse:
    """
    Standard response object returned by AI provider classes.
    """

    success: bool
    text: str
    raw_response: Any | None = None
    error: str | None = None


class BaseAIProvider(ABC):
    """
    Provider interface for AI services.

    The orchestrator should depend on this interface, not directly on OpenAI,
    Claude, Gemini, or Grok. That makes it easier to add providers later.
    """

    @abstractmethod
    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> AIProviderResponse:
        """
        Generate text from an AI provider.

        Args:
            system_prompt:
                High-level behavior/instruction prompt.

            user_prompt:
                User/task prompt.

        Returns:
            AIProviderResponse
        """
        raise NotImplementedError