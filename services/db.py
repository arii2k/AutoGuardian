from flask_sqlalchemy import SQLAlchemy
from flask import Flask
from datetime import datetime
from services.models import ScannedEmail

db = SQLAlchemy()

def init_db(app: Flask):
    """
    Initialize SQLAlchemy with the Flask app.
    """
    app.config.setdefault("SQLALCHEMY_DATABASE_URI", "sqlite:///C:/Users/Ari/Downloads/AutoGuardian/backend/autoguardian.db")
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    db.init_app(app)

def save_scan_result(sender: str,
                     subject: str,
                     score: int,
                     matched_rules: list,
                     memory_alert: str = None,
                     community_alert: str = None,
                     quarantine: bool = False):
    """
    Save a scanned email to the database, matching the ScannedEmail model.
    """
    email = ScannedEmail(
        sender=sender,
        subject=subject,
        score=score,
        matched_rules=matched_rules,
        memory_alert=memory_alert,
        community_alert=community_alert,
        quarantine=quarantine,
        timestamp=datetime.utcnow()
    )
    db.session.add(email)
    db.session.commit()
