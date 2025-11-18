# services/linguistic_guard.py
import unicodedata
import re

def detect_homoglyph_attack(text):
    """
    Detects suspicious mix of Cyrillic, Greek, or Latin lookalike characters.
    Returns (bool, message)
    """
    if not text:
        return False, ""
    
    # Normalize to NFKC (consistent unicode)
    normalized = unicodedata.normalize("NFKC", text)
    if normalized != text:
        return True, "Unicode normalization mismatch (possible disguised characters)"

    # Count scripts
    scripts = {"Latin": 0, "Cyrillic": 0, "Greek": 0}
    for ch in text:
        try:
            name = unicodedata.name(ch)
            for s in scripts:
                if s in name:
                    scripts[s] += 1
        except ValueError:
            pass

    active_scripts = [k for k, v in scripts.items() if v > 0]
    if len(active_scripts) > 1:
        return True, f"Mixed character scripts detected: {', '.join(active_scripts)}"

    # Suspicious invisible / RTL chars
    if re.search(r"[\u200B-\u200F\u202A-\u202E]", text):
        return True, "Contains invisible or direction control characters"

    return False, ""
