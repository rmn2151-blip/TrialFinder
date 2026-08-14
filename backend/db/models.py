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

    # Email verification. Stored hashed for the same reason as the reset code.
    email_verified = Column(Integer, default=0, nullable=False)  # 0/1 int for SQLite
    verification_code_hash = Column(String(255), nullable=True)
    verification_sent_at = Column(DateTime, nullable=True)

    # Password reset. The code is stored hashed so a database leak does not
    # hand an attacker working reset codes.
    reset_code_hash = Column(String(255), nullable=True)
    reset_sent_at = Column(DateTime, nullable=True)

    # Brute-force protection. Cleared on any successful login.
    failed_login_count = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)

    # Bumped on logout, password reset, and password change. Tokens carry this
    # value and are rejected when it no longer matches, which gives us real
    # server-side revocation instead of relying on the client to forget a JWT.
    token_version = Column(Integer, default=0, nullable=False)

    # Email alert preferences. The token allows one-click unsubscribe from an
    # email without logging in, which is both expected behaviour and a legal
    # requirement for bulk email in most jurisdictions.
    email_alerts_enabled = Column(Integer, default=1, nullable=False)
    unsubscribe_token = Column(String(64), nullable=True, index=True)

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
    alerts = relationship(
        "TrialAlert",
        back_populates="watched_trial",
        cascade="all, delete-orphan",
    )

    def snapshot(self) -> dict:
        """The stored state, in the same shape ctgov_service returns."""
        return {
            "status": self.last_status,
            "phase": self.last_phase,
            "completion_date": self.last_completion_date,
            "site_count": self.last_site_count,
        }


class TrialAlert(Base):
    """
    One detected change on a watched trial.

    Persisting alerts rather than only emailing them gives us three things:
    an in-app feed the user sees on next login, a dedupe key so the same
    change is never emailed twice, and an audit trail of what we told people.
    """

    __tablename__ = "trial_alerts"
    __table_args__ = (
        # A given change on a given trial is recorded once.
        UniqueConstraint(
            "watched_trial_id", "change_hash", name="uq_alert_trial_change"
        ),
    )

    id = Column(Integer, primary_key=True)
    watched_trial_id = Column(
        Integer,
        ForeignKey("watched_trials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    nct_id = Column(String(11), nullable=False)
    trial_title = Column(Text, nullable=False)
    profile_label = Column(String(120), nullable=True)
    source_url = Column(Text, nullable=True)

    # "status" | "phase" | "completion_date" | "site_count" | "results"
    change_type = Column(String(40), nullable=False)
    # Human-readable, e.g. "Status: Recruiting -> Active, not recruiting"
    description = Column(Text, nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    # "high" for things that change what a patient should do (recruitment
    # closing, results published), "normal" for everything else.
    severity = Column(String(20), default="normal", nullable=False)

    # Deduplication: sha256 of (change_type, old, new).
    change_hash = Column(String(64), nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    emailed_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)

    watched_trial = relationship("WatchedTrial", back_populates="alerts")
