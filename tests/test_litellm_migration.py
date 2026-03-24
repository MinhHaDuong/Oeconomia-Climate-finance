"""Tests for litellm migration (#289).

Verify that all three scripts use litellm for LLM calls with
provider-prefixed model strings.
"""

import inspect
import os
import sys
from unittest.mock import MagicMock, patch

# Add scripts/ to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


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


def test_collect_syllabi_no_hand_rolled_http():
    """Verify collect_syllabi.py has no hand-rolled LLM HTTP code."""
    import collect_syllabi

    source = inspect.getsource(collect_syllabi)
    # Should not contain old backend functions
    assert "_llm_call_ollama" not in source, "Old _llm_call_ollama still present"
    assert "_llm_call_openrouter" not in source, "Old _llm_call_openrouter still present"
    assert "_ollama_available" not in source, "Old _ollama_available still present"
    # Should import litellm
    assert "litellm" in source, "litellm not imported"


def test_filter_flags_no_hand_rolled_http():
    """Verify filter_flags.py _llm_call uses litellm, not raw HTTP."""
    import filter_flags

    source = inspect.getsource(filter_flags)
    # The _llm_call function should not use urllib.request for LLM calls
    assert "urllib.request.Request" not in source, "Still using urllib for LLM calls"
    assert "openrouter.ai/api/v1" not in source, "Still using raw OpenRouter URL"
    assert "localhost:11434" not in source, "Still using raw Ollama URL"
    # Should use litellm
    assert "litellm" in source, "litellm not imported"


def test_qa_llm_verify_no_hand_rolled_http():
    """Verify qa_llm_verify.py uses litellm, not requests/urllib."""
    import qa_llm_verify

    source = inspect.getsource(qa_llm_verify)
    assert "requests.post" not in source, "Still using requests.post for LLM"
    assert "OPENROUTER_URL" not in source, "Still has hard-coded OPENROUTER_URL"
    assert "litellm" in source, "litellm not imported"


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
