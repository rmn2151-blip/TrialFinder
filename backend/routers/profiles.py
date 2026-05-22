"""
Patient profile endpoints (all require auth). One account can manage many
profiles, e.g. a caregiver tracking trials for several family members.

  POST   /api/profiles        — create a profile
  GET    /api/profiles        — list this account's profiles
  GET    /api/profiles/{id}   — get one
  PUT    /api/profiles/{id}   — update
  DELETE /api/profiles/{id}   — delete
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Account
from models.profile import ProfileCreate, ProfileOut, ProfileUpdate
from routers.security import get_current_account
from services import profile_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.post("", response_model=ProfileOut, status_code=201)
def create(
    body: ProfileCreate,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    profile = profile_service.create_profile(db, account.id, body.model_dump())
    db.commit()
    db.refresh(profile)
    return profile


@router.get("", response_model=list[ProfileOut])
def list_all(
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    return profile_service.list_profiles(db, account.id)


@router.get("/{profile_id}", response_model=ProfileOut)
def get_one(
    profile_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    profile = profile_service.get_owned_profile(db, account.id, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/{profile_id}", response_model=ProfileOut)
def update(
    profile_id: int,
    body: ProfileUpdate,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    profile = profile_service.get_owned_profile(db, account.id, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile_service.update_profile(db, profile, body.model_dump())
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=204)
def delete(
    profile_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    profile = profile_service.get_owned_profile(db, account.id, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile_service.delete_profile(db, profile)
    db.commit()
    return None
