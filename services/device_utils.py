# services/device_utils.py
import os
import torch
from typing import Dict, Any

def get_device(preferred: str = None) -> torch.device:
    """
    Decide the torch.device to use.
    - preferred: "cuda", "cpu", or None (auto)
    Returns a torch.device instance.
    """
    pref = (preferred or os.environ.get("AG_DEVICE") or "auto").lower()
    if pref == "cpu":
        return torch.device("cpu")
    if pref in ("cuda", "gpu"):
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # auto
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")

def optimize_torch_for_device(device: torch.device, cpu_threads: int = None) -> Dict[str, Any]:
    """
    Apply some global perf tweaks. Returns info dict for logging.
    """
    info = {}
    if device.type == "cpu":
        if cpu_threads is None:
            cpu_threads = int(os.environ.get("AG_CPU_THREADS", "4"))
        torch.set_num_threads(cpu_threads)
        torch.set_num_interop_threads(cpu_threads)
        info["cpu_threads"] = cpu_threads
    else:
        torch.backends.cudnn.benchmark = True
        info["cudnn_benchmark"] = True
    info["device"] = str(device)
    return info
