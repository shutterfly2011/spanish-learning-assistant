import json
import os
from typing import Generator

from .base import LLMClient


class BedrockClient(LLMClient):
    """Amazon Bedrock LLM client for Claude models."""

    def __init__(
        self,
        model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        region: str = "us-east-1",
    ):
        self.model_id = model_id
        self.region = region
        self._client = None

    def _get_client(self):
        """Lazy initialization of boto3 client."""
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self.region,
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            )
        return self._client

    def chat(self, messages: list[dict], system_prompt: str = "") -> str:
        """Send messages to Bedrock and get a complete response."""
        client = self._get_client()

        # Format messages for Claude on Bedrock
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg["role"],
                "content": [{"type": "text", "text": msg["content"]}]
            })

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": formatted_messages,
        }

        if system_prompt:
            body["system"] = system_prompt

        try:
            response = client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            content = response_body.get("content", [])
            if content and len(content) > 0:
                return content[0].get("text", "")
            return ""

        except Exception as e:
            raise ConnectionError(f"Failed to connect to Bedrock: {e}")

    def chat_stream(
        self, messages: list[dict], system_prompt: str = ""
    ) -> Generator[str, None, None]:
        """Stream messages from Bedrock."""
        client = self._get_client()

        # Format messages for Claude on Bedrock
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg["role"],
                "content": [{"type": "text", "text": msg["content"]}]
            })

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": formatted_messages,
        }

        if system_prompt:
            body["system"] = system_prompt

        try:
            response = client.invoke_model_with_response_stream(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )

            for event in response.get("body", []):
                chunk = event.get("chunk")
                if chunk:
                    chunk_data = json.loads(chunk.get("bytes", b"{}").decode())
                    if chunk_data.get("type") == "content_block_delta":
                        delta = chunk_data.get("delta", {})
                        text = delta.get("text", "")
                        if text:
                            yield text

        except Exception as e:
            raise ConnectionError(f"Failed to stream from Bedrock: {e}")

    def is_available(self) -> bool:
        """Check if Bedrock is available (credentials are set)."""
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

        if not access_key or not secret_key:
            return False

        try:
            # Try to initialize the client
            self._get_client()
            return True
        except Exception:
            return False
