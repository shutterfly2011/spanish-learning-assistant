import os
from typing import Generator, Optional

from llm.base import LLMClient


class BedrockClient(LLMClient):
    """Amazon Bedrock LLM client for Claude models using API key authentication."""

    def __init__(
        self,
        model_id: str = "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        region: str = "us-east-1",
        api_key: Optional[str] = None,
    ):
        self.model_id = model_id
        self.region = region
        # Use provided API key or fall back to environment variable
        self.api_key = api_key or os.getenv("AWS_BEARER_TOKEN_BEDROCK")
        self._client = None

    def _get_client(self):
        """Lazy initialization of boto3 client with API key authentication."""
        if self._client is None:
            import boto3

            # Set the bearer token environment variable for boto3
            if self.api_key:
                os.environ["AWS_BEARER_TOKEN_BEDROCK"] = self.api_key

            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self.region,
            )
        return self._client

    def chat(self, messages: list[dict], system_prompt: str = "") -> str:
        """Send messages to Bedrock and get a complete response using the Converse API."""
        client = self._get_client()

        # Format messages for the Converse API
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg["role"],
                "content": [{"text": msg["content"]}]
            })

        # Build the request
        request = {
            "modelId": self.model_id,
            "messages": formatted_messages,
        }

        if system_prompt:
            request["system"] = [{"text": system_prompt}]

        try:
            response = client.converse(**request)

            # Extract the response text
            output = response.get("output", {})
            message = output.get("message", {})
            content = message.get("content", [])

            if content and len(content) > 0:
                return content[0].get("text", "")
            return ""

        except Exception as e:
            raise ConnectionError(f"Failed to connect to Bedrock: {e}")

    def chat_stream(
        self, messages: list[dict], system_prompt: str = ""
    ) -> Generator[str, None, None]:
        """Stream messages from Bedrock using the Converse Stream API."""
        client = self._get_client()

        # Format messages for the Converse API
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg["role"],
                "content": [{"text": msg["content"]}]
            })

        # Build the request
        request = {
            "modelId": self.model_id,
            "messages": formatted_messages,
        }

        if system_prompt:
            request["system"] = [{"text": system_prompt}]

        try:
            response = client.converse_stream(**request)

            for event in response.get("stream", []):
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"].get("delta", {})
                    text = delta.get("text", "")
                    if text:
                        yield text

        except Exception as e:
            raise ConnectionError(f"Failed to stream from Bedrock: {e}")

    def is_available(self) -> bool:
        """Check if Bedrock is available (API key is set)."""
        if not self.api_key:
            return False

        try:
            self._get_client()
            return True
        except Exception:
            return False
