# services/ai_model.py — Premium Threat Scoring Engine
import logging
import torch
from services.model_loader import ZERO_SHOT_MODEL, TRANSFORMER_MODEL, load_models
from services.device_utils import get_device

logger = logging.getLogger("AIModel")
logger.setLevel(logging.INFO)

# ---------------------------
# Configurable weights
# ---------------------------
ZERO_SHOT_WEIGHT = 0.6
TRANSFORMER_WEIGHT = 0.4

# ---------------------------
# Compute threat index
# ---------------------------
def compute_threat_index(scan_results=None, device=None):
    """
    Compute average threat index from scan results using Zero-Shot and Transformer models.

    Args:
        scan_results (list): List of emails dicts with keys like 'Subject', 'From', 'Body'
        device (torch.device): Optional, auto-selected if None

    Returns:
        float: Average threat score (0-100)
    """
    device = device or get_device()

    # Ensure models are loaded
    if ZERO_SHOT_MODEL is None or TRANSFORMER_MODEL is None:
        load_models(device=device)

    if not scan_results:
        return 0.0

    total_score = 0.0
    for email in scan_results:
        # Flexible input
        text = " ".join([str(email.get(f, "")) for f in ["Subject", "From", "Body"] if email.get(f)])
        if not text.strip():
            logger.warning(f"Skipping email with no content: {email}")
            continue

        zero_shot_score = 0.0
        transformer_score = 0.0

        # ---- Zero-Shot Scoring ----
        if ZERO_SHOT_MODEL:
            try:
                res = ZERO_SHOT_MODEL(
                    text,
                    candidate_labels=["phishing", "spam", "legitimate"],
                    device=device
                )
                if "phishing" in res['labels']:
                    idx = res['labels'].index("phishing")
                    zero_shot_score = res['scores'][idx] * 100
                else:
                    zero_shot_score = max(res['scores']) * 100
            except Exception as e:
                logger.warning(f"Zero-Shot model failed for '{text}': {e}")
                zero_shot_score = email.get("score", 0)

        # ---- Transformer Scoring ----
        if TRANSFORMER_MODEL:
            try:
                inputs = TRANSFORMER_MODEL.tokenizer(text, return_tensors="pt").to(device)
                outputs = TRANSFORMER_MODEL.model(**inputs)
                logits = outputs.logits.detach()

                # Multi-class -> softmax; binary -> sigmoid
                if logits.shape[1] > 1:
                    probs = torch.softmax(logits, dim=1)
                    # Assume phishing class is 0 (adjust if different)
                    transformer_score = probs[:, 0].item() * 100
                else:
                    transformer_score = torch.sigmoid(logits).item() * 100
            except Exception as e:
                logger.warning(f"Transformer model failed for '{text}': {e}")

        # ---- Combine scores ----
        if zero_shot_score and transformer_score:
            score = ZERO_SHOT_WEIGHT * zero_shot_score + TRANSFORMER_WEIGHT * transformer_score
        elif zero_shot_score:
            score = zero_shot_score
        elif transformer_score:
            score = transformer_score
        else:
            # fallback to email score
            score = float(email.get("score", 0))

        # Clamp 0-100
        score = max(0.0, min(100.0, score))
        total_score += score

    return total_score / len(scan_results) if scan_results else 0.0
