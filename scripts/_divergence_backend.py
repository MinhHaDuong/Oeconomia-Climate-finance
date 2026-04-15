"""Backend dispatch for divergence computations (CPU / CUDA).

Private module — called by _divergence_semantic.py.

Resolves the ``backend`` key from config/analysis.yaml:
  auto  → CUDA if torch+CUDA available, else NumPy
  cpu   → NumPy only
  cuda  → torch CUDA (raises if unavailable)
"""

from utils import get_logger

log = get_logger("_divergence_backend")

_TORCH_AVAILABLE: bool | None = None
_RESOLVED_BACKEND: str | None = None
_VALID_BACKENDS = {"auto", "cpu", "cuda"}


def _probe_torch() -> bool:
    """Lazy-check whether torch with CUDA is importable."""
    global _TORCH_AVAILABLE
    if _TORCH_AVAILABLE is None:
        try:
            import torch

            _TORCH_AVAILABLE = torch.cuda.is_available()
            if _TORCH_AVAILABLE:
                log.info(
                    "torch %s, CUDA device: %s",
                    torch.__version__,
                    torch.cuda.get_device_name(0),
                )
            else:
                log.info("torch available but no CUDA — using NumPy")
        except ImportError:
            _TORCH_AVAILABLE = False
            log.info("torch not installed — using NumPy")
    return _TORCH_AVAILABLE


def get_backend(cfg: dict) -> str:
    """Return 'torch' or 'numpy' based on config and hardware.

    Parameters
    ----------
    cfg : dict
        Full analysis config (reads ``cfg["divergence"]["backend"]``).

    Returns
    -------
    str
        ``"torch"`` or ``"numpy"``.

    Raises
    ------
    RuntimeError
        If ``backend: cuda`` but no CUDA-capable torch is found.

    """
    global _RESOLVED_BACKEND
    if _RESOLVED_BACKEND is not None:
        return _RESOLVED_BACKEND

    setting = cfg["divergence"].get("backend", "auto")
    if setting not in _VALID_BACKENDS:
        raise ValueError(
            f"Invalid backend {setting!r}, must be one of {_VALID_BACKENDS}"
        )

    if setting == "cpu":
        result = "numpy"
    elif setting == "cuda":
        if not _probe_torch():
            raise RuntimeError(
                "Config requires backend: cuda but torch CUDA is not available"
            )
        result = "torch"
    else:
        # auto
        result = "torch" if _probe_torch() else "numpy"

    log.info("Divergence backend: %s (config: %s)", result, setting)
    _RESOLVED_BACKEND = result
    return result


def to_tensor(arr: "np.ndarray") -> "torch.Tensor":
    """Convert NumPy array to float32 torch tensor on CUDA."""
    import torch

    return torch.as_tensor(arr, dtype=torch.float32, device="cuda")
