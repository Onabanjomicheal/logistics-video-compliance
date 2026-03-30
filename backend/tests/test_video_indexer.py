import os
import pytest

from backend.src.services.vision_analysis import VisionAnalyzer
from backend.src.services.rag_retriever import RulesRetriever


def test_vision_analyzer_requires_env(monkeypatch):
    monkeypatch.delenv("AZURE_VISION_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_VISION_KEY", raising=False)
    with pytest.raises(RuntimeError):
        VisionAnalyzer()


def test_rules_retriever_requires_env(monkeypatch):
    monkeypatch.delenv("AZURE_SEARCH_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_SEARCH_INDEX_NAME", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)
    with pytest.raises(RuntimeError):
        RulesRetriever()
