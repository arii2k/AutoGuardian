from transformers import pipeline
import torch

device = 0 if torch.cuda.is_available() else -1
print("Using device:", "cuda" if device == 0 else "cpu")

print("Downloading facebook/bart-large-mnli ...")
pipe = pipeline("zero-shot-classification", model="facebook/bart-large-mnli", device=device)
print("✅ Zero-shot model loaded!")

print("Downloading distilbert-base-uncased-finetuned-sst-2-english ...")
pipe2 = pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english", device=device)
print("✅ Transformer model loaded!")
