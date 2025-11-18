from services.ai_ensemble import ensemble_score_with_reasons

sample_email = {
    "Subject": "Important: Verify your account now",
    "Body": "Please click this link to verify your account: http://phishingsite.com",
    "From": "security@paypal.fake"
}

score, reasons = ensemble_score_with_reasons(sample_email)
print(f"\n🧠 Hybrid Score: {score}")
print("Reasons:")
for r in reasons:
    print(" -", r)
