# backend/ai_detector.py — Premium Multi-Model Phishing/NLP Detector
import re
import html
import json
import subprocess
import sys
import tempfile
import torch
import torch.nn.functional as F
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification

# ----------------------------
# DEVICE SETUP (GPU if available)
# ----------------------------
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[ai_detector] Using device: {DEVICE}")

# ----------------------------
# Zero-Shot Ensemble
# ----------------------------
ZERO_SHOT_MODELS = [
    "facebook/bart-large-mnli",
    "roberta-large-mnli"
]
zero_shot_classifiers = []
for model_name in ZERO_SHOT_MODELS:
    try:
        classifier = pipeline("zero-shot-classification", model=model_name, device=0 if DEVICE.type=="cuda" else -1)
        zero_shot_classifiers.append(classifier)
        print(f"[ai_detector] ✅ Zero-shot model loaded: {model_name}")
    except Exception as e:
        print(f"[ai_detector] ⚠️ Failed to load zero-shot model {model_name}: {e}")

ZERO_SHOT_OK = len(zero_shot_classifiers) > 0

# ----------------------------
# Transformer Model Config
# ----------------------------
TRANSFORMER_MODELS = [
    "microsoft/deberta-v3-small",
    # add more models for premium ensemble
]
CLASS_MAPPING = {0: "Safe", 1: "Suspicious", 2: "High Risk"}

# ----------------------------
# Email Preprocessing
# ----------------------------
def clean_email_text(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def extract_features(email_obj: dict):
    """Extract basic features for scoring heuristics."""
    text = clean_email_text(email_obj.get("Subject", "") + " " + email_obj.get("Body", ""))
    urls = re.findall(r"https?://\S+", text)
    suspicious_domains = [url.split("/")[2] for url in urls if "paypal" in url.lower() or "bank" in url.lower()]
    return {
        "text": text,
        "url_count": len(urls),
        "suspicious_domains": suspicious_domains
    }

# ----------------------------
# Zero-Shot Detection (multi-model)
# ----------------------------
def detect_phishing(email_obj: dict, candidate_labels=None):
    if not ZERO_SHOT_OK:
        return {"score": 0, "risk_level": "Unknown", "labels": [], "explanation": "Zero-shot unavailable"}
    
    candidate_labels = candidate_labels or ["phishing", "spam", "legitimate"]
    features = extract_features(email_obj)
    text = features["text"]

    # Ensemble scoring across models
    scores = []
    labels_collected = []
    for clf in zero_shot_classifiers:
        try:
            res = clf(text, candidate_labels=candidate_labels)
            scores.append(res)
            labels_collected.extend(res["labels"])
        except Exception as e:
            print(f"[ai_detector] ❌ Zero-shot failed: {e}")

    # Average phishing score across models
    phishing_scores = []
    for res in scores:
        idx = res["labels"].index("phishing") if "phishing" in res["labels"] else -1
        if idx >= 0:
            phishing_scores.append(res["scores"][idx])
    avg_score = round(sum(phishing_scores)/len(phishing_scores) * 100, 2) if phishing_scores else 0

    # Dynamic risk level thresholds
    if avg_score < 20:
        risk_level = "Safe"
    elif avg_score < 60:
        risk_level = "Suspicious"
    else:
        risk_level = "High Risk"

    return {
        "score": avg_score,
        "risk_level": risk_level,
        "labels": list(set(labels_collected)),
        "keywords_detected": re.findall(r"\b(paypal|bank|verify|urgent)\b", text, flags=re.I),
        "suspicious_links": features["suspicious_domains"],
        "explanation": "Zero-shot ensemble scoring"
    }

# ----------------------------
# Transformer Scoring (subprocess-safe)
# ----------------------------
def nlp_score_email(email_obj: dict, timeout_sec=15):
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8")
        json.dump(email_obj, tmp)
        tmp.close()

        cmd = [sys.executable, __file__, "--infer", tmp.name]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        if result.returncode != 0:
            return 0, "Error", f"Child failed: {result.stderr.strip()[:200]}"
        out = json.loads(result.stdout.strip())
        return out.get("score", 0), out.get("risk_level", "Unknown"), out.get("explanation", "")
    except subprocess.TimeoutExpired:
        return 0, "Timeout", "Transformer subprocess timed out."
    except Exception as e:
        return 0, "Error", f"Subprocess error: {e}"

# ----------------------------
# Child process inference
# ----------------------------
def _child_infer(json_path: str):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            email_obj = json.load(f)

        text = clean_email_text(email_obj.get("Subject", "") + " " + email_obj.get("Body", ""))
        tokenizer = AutoTokenizer.from_pretrained(TRANSFORMER_MODELS[0])
        model = AutoModelForSequenceClassification.from_pretrained(TRANSFORMER_MODELS[0], num_labels=3)
        model.to(DEVICE)
        model.eval()

        inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=512).to(DEVICE)
        with torch.no_grad():
            outputs = model(**inputs)
            probs = F.softmax(outputs.logits, dim=-1).squeeze().tolist()

        class_idx = int(torch.argmax(outputs.logits))
        risk_level = CLASS_MAPPING.get(class_idx, "Safe")
        score = round(float(probs[class_idx])*100,2)
        explanation = f"Predicted as {risk_level} (p={probs[class_idx]:.2f})"

        print(json.dumps({
            "score": score,
            "risk_level": risk_level,
            "explanation": explanation,
            "probabilities": probs
        }))
    except Exception as e:
        print(json.dumps({"score": 0, "risk_level": "Error", "explanation": str(e)}))
        sys.exit(1)

# ----------------------------
# Hybrid scoring combining Zero-Shot + Transformer
# ----------------------------
def hybrid_score(email_obj: dict):
    zs_result = detect_phishing(email_obj)
    tf_score, tf_level, tf_expl = nlp_score_email(email_obj)
    # Weighted average (adjustable)
    final_score = round((zs_result["score"]*0.6 + tf_score*0.4), 2)
    if final_score < 20:
        risk_level = "Safe"
    elif final_score < 60:
        risk_level = "Suspicious"
    else:
        risk_level = "High Risk"

    zs_result["hybrid_score"] = final_score
    zs_result["hybrid_risk_level"] = risk_level
    zs_result["transformer_explanation"] = tf_expl
    return zs_result

# ----------------------------
# Manual test & CLI
# ----------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--infer", type=str, help="Path to JSON file for subprocess")
    args = parser.parse_args()

    if args.infer:
        _child_infer(args.infer)
        sys.exit(0)

    # Test email
    test_email = {
        "Subject": "URGENT: Verify your PayPal account",
        "Body": "We noticed suspicious activity. Log in now to confirm.",
        "From": "security@paypal.com"
    }

    print("=== Zero-Shot ===")
    print(detect_phishing(test_email))

    print("\n=== Transformer (subprocess) ===")
    print(nlp_score_email(test_email))

    print("\n=== Hybrid Score ===")
    print(hybrid_score(test_email))
