"""Backend dispatch for divergence computations (CPU / CUDA).

Private module — called by _divergence_semantic.py.

Resolves the ``backend`` key from config/analysis.yaml:
  auto  → CUDA if torch+CUDA available, else NumPy
  cpu   → NumPy only
  cuda  → torch CUDA (raises if unavailable)
"""

import numpy as np
from utils import get_logger

log = get_logger("_divergence_backend")

_TORCH_AVAILABLE: bool | None = None
_DEVICE: str | None = None


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
    setting = cfg["divergence"].get("backend", "auto")

    if setting == "cpu":
        log.info("Backend forced to NumPy (config: cpu)")
        return "numpy"

    has_cuda = _probe_torch()

    if setting == "cuda":
        if not has_cuda:
            raise RuntimeError(
                "Config requires backend: cuda but torch CUDA is not available"
            )
        return "torch"

    # auto
    return "torch" if has_cuda else "numpy"


def to_tensor(arr: np.ndarray) -> "torch.Tensor":
    """Convert NumPy array to float32 torch tensor on CUDA."""
    import torch

    return torch.as_tensor(arr, dtype=torch.float32, device="cuda")


def to_numpy(t: "torch.Tensor") -> np.ndarray:
    """Move torch tensor back to NumPy on CPU."""
    return t.detach().cpu().numpy()
