from abc import ABC, abstractmethod
from typing import Generator


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def chat(self, messages: list[dict], system_prompt: str = "") -> str:
        """Send messages to the LLM and get a response.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
                     Roles are 'user' or 'assistant'.
            system_prompt: Optional system prompt to guide the model's behavior.

        Returns:
            The assistant's response as a string.
        """
        pass

    @abstractmethod
    def chat_stream(
        self, messages: list[dict], system_prompt: str = ""
    ) -> Generator[str, None, None]:
        """Stream messages from the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            system_prompt: Optional system prompt to guide the model's behavior.

        Yields:
            Chunks of the assistant's response.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the LLM service is available and properly configured."""
        pass
