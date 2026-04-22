"""TDD guard: LOW_N_LEXICAL_THRESHOLD must be defined in _divergence_lexical.py."""


def test_l1_has_low_n_lexical_threshold():
    """_divergence_lexical.py must define LOW_N_LEXICAL_THRESHOLD."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_divergence_lexical",
        "scripts/_divergence_lexical.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "LOW_N_LEXICAL_THRESHOLD"), (
        "LOW_N_LEXICAL_THRESHOLD not defined in _divergence_lexical.py"
    )
    assert mod.LOW_N_LEXICAL_THRESHOLD == 50
