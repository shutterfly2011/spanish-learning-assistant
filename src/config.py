import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import yaml
from dotenv import load_dotenv

load_dotenv()


@dataclass
class OllamaConfig:
    base_url: str = "http://localhost:11434"
    model: str = "llama3"


@dataclass
class BedrockConfig:
    model_id: str = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    region: str = "us-east-1"


@dataclass
class AppConfig:
    llm_provider: str = "ollama"  # "ollama" or "bedrock"
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    bedrock: BedrockConfig = field(default_factory=BedrockConfig)
    cefr_level: str = "all"  # "all", "A1", "A2", "B1", "B2", "C1", "C2"


def load_config_from_yaml(config_path: Optional[str] = None) -> dict:
    """Load configuration from YAML file if it exists."""
    if config_path is None:
        config_path = os.getenv("CONFIG_PATH", "config.yaml")

    path = Path(config_path)
    if path.exists():
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def load_config() -> AppConfig:
    """Load configuration from environment variables and config file.

    Priority: Environment variables > Config file > Defaults
    """
    yaml_config = load_config_from_yaml()

    # Ollama config
    ollama_config = OllamaConfig(
        base_url=os.getenv(
            "OLLAMA_BASE_URL",
            yaml_config.get("ollama", {}).get("base_url", "http://localhost:11434")
        ),
        model=os.getenv(
            "OLLAMA_MODEL",
            yaml_config.get("ollama", {}).get("model", "llama3")
        ),
    )

    # Bedrock config
    bedrock_config = BedrockConfig(
        model_id=os.getenv(
            "BEDROCK_MODEL_ID",
            yaml_config.get("bedrock", {}).get("model_id", "us.anthropic.claude-3-5-sonnet-20241022-v2:0")
        ),
        region=os.getenv(
            "AWS_REGION",
            yaml_config.get("bedrock", {}).get("region", "us-east-1")
        ),
    )

    # App config
    app_config = AppConfig(
        llm_provider=os.getenv(
            "LLM_PROVIDER",
            yaml_config.get("llm_provider", "ollama")
        ),
        ollama=ollama_config,
        bedrock=bedrock_config,
        cefr_level=yaml_config.get("cefr_level", "all"),
    )

    return app_config


def get_aws_credentials() -> tuple[Optional[str], Optional[str]]:
    """Get AWS credentials from environment variables only (for security)."""
    return (
        os.getenv("AWS_ACCESS_KEY_ID"),
        os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


def has_aws_credentials() -> bool:
    """Check if AWS credentials are available."""
    access_key, secret_key = get_aws_credentials()
    return bool(access_key and secret_key)
