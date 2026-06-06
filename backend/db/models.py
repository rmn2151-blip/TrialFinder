"""
SQLAlchemy ORM models.

Account hierarchy (caregiver-ready):
    Account (login: email + password)
      └── PatientProfile (e.g. "Mom", "Myself", "Dad")
            └── WatchedTrial (a saved trial, monitored for changes)

One account can hold many patient profiles, so an adult child can manage
trials for several family members under a single login. Alerts go to the
account's email.
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from db.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    email = Column(String(320), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    profiles = relationship(
        "PatientProfile",
        back_populates="account",
        cascade="all, delete-orphan",
    )


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    id = Column(Integer, primary_key=True)
    account_id = Column(
        Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    label = Column(String(120), nullable=False)  # e.g. "Mom", "Myself"
    condition = Column(Text, nullable=False)
    treatment_history = Column(Text, nullable=True)
    location = Column(String(200), nullable=False)
    age = Column(Integer, nullable=True)
    medications = Column(JSON, default=list, nullable=False)
    biomarkers = Column(JSON, default=list, nullable=False)
    last_treatment_date = Column(String(10), nullable=True)
    additional_context = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="profiles")
    watched_trials = relationship(
        "WatchedTrial",
        back_populates="profile",
        cascade="all, delete-orphan",
    )


class WatchedTrial(Base):
    __tablename__ = "watched_trials"
    __table_args__ = (
        UniqueConstraint("profile_id", "nct_id", name="uq_profile_trial"),
    )

    id = Column(Integer, primary_key=True)
    profile_id = Column(
        Integer, ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    nct_id = Column(String(11), nullable=False, index=True)
    title = Column(Text, nullable=False)
    source_url = Column(Text, nullable=True)

    # Snapshot of the last-known state, used for change detection.
    last_status = Column(String(80), nullable=True)
    last_phase = Column(String(40), nullable=True)
    last_completion_date = Column(String(40), nullable=True)
    last_site_count = Column(Integer, nullable=True)

    # Trial result tracker — populated when status flips to Completed.
    results_headline = Column(Text, nullable=True)
    results_summary = Column(Text, nullable=True)
    results_journal_url = Column(Text, nullable=True)
    results_fetched_at = Column(DateTime, nullable=True)

    # Enrollment status tracker
    enrollment_status = Column(String(40), nullable=True, default="interested")
    enrollment_changed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_checked_at = Column(DateTime, nullable=True)
    last_change_at = Column(DateTime, nullable=True)

    profile = relationship("PatientProfile", back_populates="watched_trials")

    def snapshot(self) -> dict:
        """The stored state, in the same shape ctgov_service returns."""
        return {
            "status": self.last_status,
            "phase": self.last_phase,
            "completion_date": self.last_completion_date,
            "site_count": self.last_site_count,
        }
