"""Runtime provider settings. Gemini Live remains the default; Azure OpenAI is opt-in."""

from __future__ import annotations

import os


def provider() -> str:
    return os.getenv("LLM_PROVIDER", "gemini").strip().lower()


def is_azure() -> bool:
    return provider() in {"azure", "azure_openai", "azure-openai"}


def azure_api_key() -> str:
    return os.getenv("AZURE_OPENAI_API_KEY", "").strip()


def azure_endpoint() -> str:
    return os.getenv("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")


def azure_api_version() -> str:
    return os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview").strip()


def azure_deployment() -> str:
    return os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip()


def azure_embedding_deployment() -> str:
    return os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "").strip()


def has_credentials() -> bool:
    if is_azure():
        return bool(azure_api_key() and azure_endpoint() and azure_deployment())
    return bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))


def chat_model_id() -> str:
    if is_azure():
        return azure_deployment() or "azure-openai"
    return os.getenv("FNOL_CLAIM_MODEL", "gemini-3.8-flash")


def live_model_id() -> str:
    if is_azure():
        return azure_deployment() or "azure-openai"
    return os.getenv("FNOL_GEMINI_LIVE_MODEL", "gemini-3.8-live")


def sketch_model_id() -> str:
    if is_azure():
        return f"{azure_deployment() or 'azure-openai'} (SVG)"
    return os.getenv("FNOL_SKETCH_MODEL", "gemini-3.1-flash-image")


def voice_mode() -> str:
    return "browser" if is_azure() else "gemini_live"
