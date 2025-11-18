# services/model_loader.py — Cached Loader for Zero-Shot & Transformer Models
# ---------------------------------------------------------------------------
# Safely initializes and caches Hugging Face models across CPU/GPU devices.
# Never returns None silently — logs all load events clearly.
# ---------------------------------------------------------------------------

import os
import logging
from transformers import pipeline
from services.device_utils import get_device

# Global variables
ZERO_SHOT_MODEL = None
TRANSFORMER_MODEL = None
_LOADED_DEVICE_STR = None  # prevents reload on same device

# ---------------------------
# Logger setup
# ---------------------------
logger = logging.getLogger("AutoGuardian.ModelLoader")
logger.setLevel(logging.INFO)
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(ch)


def load_models(device=None):
    """
    Load AI models (Zero-Shot & Transformer) once and move them to the proper device.
    Supports CPU, GPU, or CUDA dynamically. Safe to call multiple times.
    Returns:
        dict: {'zero_shot': ZERO_SHOT_MODEL, 'transformer': TRANSFORMER_MODEL}
    """
    global ZERO_SHOT_MODEL, TRANSFORMER_MODEL, _LOADED_DEVICE_STR

    device = device or get_device()
    device_index = 0 if getattr(device, "type", "cpu") == "cuda" else -1
    device_str = f"{getattr(device, 'type', 'cpu')}:{device_index}"

    # Skip reload if already loaded
    if ZERO_SHOT_MODEL and TRANSFORMER_MODEL and _LOADED_DEVICE_STR == device_str:
        logger.info(f"♻️ Reusing cached models on {device_str}")
        return {"zero_shot": ZERO_SHOT_MODEL, "transformer": TRANSFORMER_MODEL}

    logger.info(f"🚀 Loading AI models on {device} ...")

    # ---- Zero-Shot Model ----
    try:
        ZERO_SHOT_MODEL = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            device=device_index
        )
        logger.info(f"✅ Zero-Shot model loaded on {device}")
    except Exception as e:
        logger.warning(f"❌ Failed to load Zero-Shot model: {e}")
        ZERO_SHOT_MODEL = None

    # ---- Transformer Model ----
    try:
        TRANSFORMER_MODEL = pipeline(
            "text-classification",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            device=device_index
        )
        logger.info(f"✅ Transformer model loaded on {device}")
    except Exception as e:
        logger.warning(f"❌ Failed to load Transformer model: {e}")
        TRANSFORMER_MODEL = None

    # ---- Fallback protection ----
    if ZERO_SHOT_MODEL is None and TRANSFORMER_MODEL is None:
        logger.error("⚠️ No models loaded! AI threat scores will remain at 0 until models initialize.")
    else:
        logger.info("🧠 AI models ready and cached for inference.")

    _LOADED_DEVICE_STR = device_str
    return {"zero_shot": ZERO_SHOT_MODEL, "transformer": TRANSFORMER_MODEL}
