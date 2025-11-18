# services/similarity_index.py — AutoGuardian Threat Similarity Index
# ------------------------------------------------------------------
# Maintains a persistent embedding index for past emails.
# Provides similarity search for template reuse detection.
# ------------------------------------------------------------------

import os
import json
from datetime import datetime, timezone
from typing import List, Dict
from sentence_transformers import SentenceTransformer, util
import torch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SIMILARITY_FILE = os.path.join(DATA_DIR, "similarity_index.json")
os.makedirs(DATA_DIR, exist_ok=True)

# Load pre-trained embedding model
MODEL = SentenceTransformer('all-MiniLM-L6-v2')

# ---------------------------
# Helpers
# ---------------------------
def _load_index() -> List[Dict]:
    if os.path.exists(SIMILARITY_FILE):
        try:
            with open(SIMILARITY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def _save_index(index: List[Dict]):
    try:
        with open(SIMILARITY_FILE, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

# ---------------------------
# Add email to similarity index
# ---------------------------
def add_email_to_index(email_obj: Dict):
    """
    Adds a new email to the similarity index.
    Replaces existing entry with same ID if present.
    """
    index = _load_index()
    text = f"{email_obj.get('Subject','')} {email_obj.get('Body','')}"
    
    # Compute embedding as list for JSON storage
    embedding = MODEL.encode(text, convert_to_tensor=True).tolist()

    # Remove existing entry with same ID if exists
    index = [item for item in index if item.get("id") != email_obj.get("id")]

    index.append({
        "id": email_obj.get("id"),
        "subject": email_obj.get("Subject",""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "embedding": embedding
    })
    _save_index(index)

# ---------------------------
# Compute similarity against index
# ---------------------------
def compute_similarity(email_obj: Dict, top_k: int = 5, min_score: float = 0.3) -> List[Dict]:
    """
    Returns top_k most similar past emails with similarity scores (0-1)
    Filters out results below min_score.
    """
    index = _load_index()
    if not index:
        return []

    text = f"{email_obj.get('Subject','')} {email_obj.get('Body','')}"
    emb = MODEL.encode(text, convert_to_tensor=True)

    results = []
    for item in index:
        past_emb_list = item.get("embedding")
        if past_emb_list:
            try:
                past_emb = torch.tensor(past_emb_list)
                score = util.cos_sim(emb, past_emb)[0][0].item()
                if score >= min_score:
                    results.append({
                        "email_id": item.get("id"),
                        "subject": item.get("subject"),
                        "timestamp": item.get("timestamp"),
                        "similarity": round(score, 3)
                    })
            except Exception:
                continue

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]

# ---------------------------
# Optional: rebuild index from a list of emails
# ---------------------------
def rebuild_index(emails: List[Dict]):
    """
    Recompute embeddings for a list of emails and save to the index.
    """
    index = []
    for email_obj in emails:
        text = f"{email_obj.get('Subject','')} {email_obj.get('Body','')}"
        embedding = MODEL.encode(text, convert_to_tensor=True).tolist()
        index.append({
            "id": email_obj.get("id"),
            "subject": email_obj.get("Subject",""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "embedding": embedding
        })
    _save_index(index)
