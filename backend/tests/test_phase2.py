"""Tests for Phase 2 utilities — token counting, LLM resolution, memory extraction."""

import pytest
from unittest.mock import patch, AsyncMock


class TestTokenCounting:
    """Tests for app.utils.tokens module."""

    def test_count_tokens_empty(self):
        from app.utils.tokens import count_tokens
        assert count_tokens("") == 0

    def test_count_tokens_basic(self):
        from app.utils.tokens import count_tokens
        result = count_tokens("Hello, world!")
        assert result > 0
        assert result < 20  # Should be ~4 tokens

    def test_count_tokens_longer_text(self):
        from app.utils.tokens import count_tokens
        short = count_tokens("Hi")
        long = count_tokens("This is a much longer sentence with many more words in it")
        assert long > short

    def test_count_messages_tokens(self):
        from app.utils.tokens import count_messages_tokens
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = count_messages_tokens(messages)
        assert result > 0
        # Each message has ~4 token overhead + content
        assert result > 8

    def test_trim_messages_within_budget(self):
        from app.utils.tokens import trim_messages_to_budget
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        result = trim_messages_to_budget(messages, budget=1000)
        assert len(result) == 2  # Both fit

    def test_trim_messages_over_budget(self):
        from app.utils.tokens import trim_messages_to_budget
        messages = [
            {"role": "user", "content": "First message " * 100},
            {"role": "user", "content": "Second message " * 100},
            {"role": "user", "content": "Third message " * 100},
            {"role": "user", "content": "Most recent"},
        ]
        result = trim_messages_to_budget(messages, budget=200)
        # Should trim but keep at least the most recent
        assert len(result) < len(messages)
        assert result[-1]["content"] == "Most recent"


class TestLLMResolver:
    """Tests for app.utils.llm module."""

    @patch("app.utils.llm.load_providers")
    def test_no_providers_returns_none(self, mock_load):
        from app.utils.llm import get_active_llm
        mock_load.return_value = {}
        assert get_active_llm() is None

    @patch("app.utils.llm.load_providers")
    def test_disabled_provider_skipped(self, mock_load):
        from app.utils.llm import get_active_llm
        mock_load.return_value = {
            "openai": {"enabled": False, "api_key": "sk-test", "model": "gpt-4"}
        }
        assert get_active_llm() is None

    @patch("app.utils.llm.load_providers")
    def test_enabled_openai_resolved(self, mock_load):
        from app.utils.llm import get_active_llm
        mock_load.return_value = {
            "openai": {"enabled": True, "api_key": "sk-test", "model": "gpt-4o"}
        }
        result = get_active_llm()
        assert result is not None
        model_str, config = result
        assert model_str == "gpt-4o"
        assert config["api_key"] == "sk-test"

    @patch("app.utils.llm.load_providers")
    def test_enabled_gemini_resolved(self, mock_load):
        from app.utils.llm import get_active_llm
        mock_load.return_value = {
            "gemini": {"enabled": True, "api_key": "key123", "model": "gemini-2.0-flash"}
        }
        result = get_active_llm()
        assert result is not None
        model_str, _ = result
        assert model_str == "gemini/gemini-2.0-flash"

    @patch("app.utils.llm.load_providers")
    def test_ollama_no_key_still_works(self, mock_load):
        from app.utils.llm import get_active_llm
        mock_load.return_value = {
            "ollama": {"enabled": True, "model": "llama3"}
        }
        result = get_active_llm()
        assert result is not None
        model_str, _ = result
        assert model_str == "ollama/llama3"


class TestMemoryExtractionRegex:
    """Tests for regex-based memory extraction (offline fallback)."""

    def test_extracts_preferences(self):
        from app.services.memory_service import _extract_facts_regex
        messages = [
            {"role": "user", "content": "I prefer Python over JavaScript for backend work"},
            {"role": "assistant", "content": "Good choice!"},
        ]
        facts = _extract_facts_regex(messages)
        assert len(facts) > 0
        assert any("Python" in f for f in facts)

    def test_extracts_job_info(self):
        from app.services.memory_service import _extract_facts_regex
        messages = [
            {"role": "user", "content": "I work at Google as a senior engineer"},
        ]
        facts = _extract_facts_regex(messages)
        assert len(facts) > 0

    def test_ignores_assistant_messages(self):
        from app.services.memory_service import _extract_facts_regex
        messages = [
            {"role": "assistant", "content": "I prefer to help you with Python"},
        ]
        facts = _extract_facts_regex(messages)
        assert len(facts) == 0

    def test_ignores_short_messages(self):
        from app.services.memory_service import _extract_facts_regex
        messages = [
            {"role": "user", "content": "hi"},
        ]
        facts = _extract_facts_regex(messages)
        assert len(facts) == 0


class TestRAGCitations:
    """Tests for RAG citation formatting."""

    def test_format_rag_context_empty(self):
        from app.routers.chat import _format_rag_context
        assert _format_rag_context([]) == ""

    def test_format_rag_context_with_results(self):
        from app.routers.chat import _format_rag_context
        results = [
            {"text": "John has 5 years of Python experience", "source_file": "resume.pdf", "score": 0.95},
            {"text": "Skills include ML and data science", "source_file": "resume.pdf", "score": 0.88},
        ]
        context = _format_rag_context(results)
        assert "[1]" in context
        assert "[2]" in context
        assert "resume.pdf" in context
        assert "cite the source" in context.lower()
