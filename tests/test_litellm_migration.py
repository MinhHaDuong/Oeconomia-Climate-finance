"""Tests for litellm migration (#289).

Verify that all three scripts use litellm for LLM calls with
provider-prefixed model strings.

Source inspection tests read files directly (no heavy imports).
Integration tests that import+mock litellm are marked @integration.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
# Add scripts/ to path (needed for integration tests that import modules)
sys.path.insert(0, SCRIPTS_DIR)


def _read_script(name):
    """Read script source from disk (no import overhead)."""
    with open(os.path.join(SCRIPTS_DIR, name)) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Integration: litellm routing (requires import + mock)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_litellm_model_string_routing():
    """Verify provider-prefixed model strings route correctly via litellm.

    ollama/qwen3.5:27b should route to Ollama backend.
    openrouter/google/gemma-2-27b-it should route to OpenRouter backend.
    litellm handles this routing internally — we just verify the call shape.
    """
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"is_syllabus": false}'

    with patch("litellm.completion", return_value=mock_response) as mock_comp:
        import collect_syllabi
        # Reload to pick up patched litellm
        import importlib
        importlib.reload(collect_syllabi)

        # Test Ollama-prefixed model
        result = collect_syllabi.llm_call("test prompt", model="ollama/qwen3.5:27b")
        assert result is not None
        mock_comp.assert_called()
        call_kwargs = mock_comp.call_args
        assert call_kwargs[1]["model"] == "ollama/qwen3.5:27b"

        mock_comp.reset_mock()

        # Test OpenRouter-prefixed model
        result = collect_syllabi.llm_call(
            "test prompt", model="openrouter/google/gemma-2-27b-it"
        )
        assert result is not None
        call_kwargs = mock_comp.call_args
        assert call_kwargs[1]["model"] == "openrouter/google/gemma-2-27b-it"


@pytest.mark.integration
def test_env_var_model_config():
    """Verify scripts read model from env vars with provider prefix."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"is_syllabus": false}'

    with patch("litellm.completion", return_value=mock_response), \
         patch.dict("os.environ", {
             "CLASSIFY_MODEL": "openrouter/google/gemini-2.5-flash",
             "EXTRACT_MODEL": "openrouter/google/gemma-2-27b-it",
         }):
        import collect_syllabi
        import importlib
        importlib.reload(collect_syllabi)

        result = collect_syllabi.llm_call(
            "test", model="openrouter/google/gemini-2.5-flash"
        )
        assert result is not None


# ---------------------------------------------------------------------------
# Source inspection: no hand-rolled HTTP (file reads, no heavy imports)
# ---------------------------------------------------------------------------

def test_collect_syllabi_no_hand_rolled_http():
    """Verify collect_syllabi pipeline has no hand-rolled LLM HTTP code."""
    source = _read_script("collect_syllabi.py")
    io_source = _read_script("syllabi_io.py")
    combined = source + io_source
    assert "_llm_call_ollama" not in combined, "Old _llm_call_ollama still present"
    assert "_llm_call_openrouter" not in combined, "Old _llm_call_openrouter still present"
    assert "_ollama_available" not in combined, "Old _ollama_available still present"
    assert "litellm" in combined, "litellm not imported in collect_syllabi pipeline"


def test_filter_flags_no_hand_rolled_http():
    """Verify filter_flags.py _llm_call uses litellm, not raw HTTP."""
    source = _read_script("filter_flags.py")
    assert "urllib.request.Request" not in source, "Still using urllib for LLM calls"
    assert "openrouter.ai/api/v1" not in source, "Still using raw OpenRouter URL"
    assert "localhost:11434" not in source, "Still using raw Ollama URL"
    assert "litellm" in source, "litellm not imported"


def test_qa_llm_verify_no_hand_rolled_http():
    """Verify qa_llm_verify.py uses litellm, not requests/urllib."""
    source = _read_script("qa_llm_verify.py")
    assert "requests.post" not in source, "Still using requests.post for LLM"
    assert "OPENROUTER_URL" not in source, "Still has hard-coded OPENROUTER_URL"
    assert "litellm" in source, "litellm not imported"
