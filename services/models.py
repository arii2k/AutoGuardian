# services/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# ---------------------------
# Base & Engine
# ---------------------------
Base = declarative_base()

# Database file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, "autoguardian.db")

# SQLite engine
engine = create_engine(f"sqlite:///{DB_FILE}", echo=False)

# Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

# ---------------------------
# ScannedEmail model
# ---------------------------
class ScannedEmail(Base):
    __tablename__ = "scanned_emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    sender = Column(String)
    subject = Column(String)
    score = Column(Integer)
    matched_rules = Column(JSON)
    memory_alert = Column(String, nullable=True)
    community_alert = Column(String, nullable=True)
    quarantine = Column(Boolean, default=False)

    def __repr__(self):
        return f"<ScannedEmail(sender={self.sender}, subject={self.subject}, score={self.score})>"

# ---------------------------
# Create tables if not exist
# ---------------------------
Base.metadata.create_all(bind=engine)
