"""CRUD for patient profiles, always scoped to an owning account."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import PatientProfile


def create_profile(db: Session, account_id: int, data: dict) -> PatientProfile:
    profile = PatientProfile(account_id=account_id, **data)
    db.add(profile)
    db.flush()
    return profile


def list_profiles(db: Session, account_id: int) -> list[PatientProfile]:
    return list(
        db.execute(
            select(PatientProfile).where(PatientProfile.account_id == account_id)
        ).scalars()
    )


def get_owned_profile(
    db: Session, account_id: int, profile_id: int
) -> Optional[PatientProfile]:
    """Return the profile only if it belongs to this account, else None."""
    profile = db.get(PatientProfile, profile_id)
    if profile is None or profile.account_id != account_id:
        return None
    return profile


def update_profile(db: Session, profile: PatientProfile, data: dict) -> PatientProfile:
    for key, value in data.items():
        setattr(profile, key, value)
    db.flush()
    return profile


def delete_profile(db: Session, profile: PatientProfile) -> None:
    db.delete(profile)
