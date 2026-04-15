from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from schemas.organization import CloudAccountCreate, CloudAccountOut
from models.cloud_account import CloudAccount
from models.organization import Organization
from models.user import User
from database import get_db
from routes.auth import get_current_user
from utils import encrypt_data


router = APIRouter()

def map_cloud_account(account: CloudAccount) -> dict:
    creds = account.credentials or {}

    return {
        "id": account.id,
        "organization_id": account.organization_id,
        "owner_id": account.owner_id,
        "tenant_id": creds.get("tenant_id"),
        "client_id": creds.get("client_id"),
        "subscription_id": creds.get("subscription_id"),
    }


@router.post("/", response_model=CloudAccountOut)
def create_cloud_account(
    account_in: CloudAccountCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    org = db.query(Organization).filter(
        Organization.id == account_in.organization_id,
        Organization.deleted_at.is_(None)
    ).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    credentials = {
        "tenant_id": account_in.tenant_id,
        "client_id": account_in.client_id,
        "client_secret": encrypt_data(account_in.client_secret),
        "subscription_id": account_in.subscription_id
    }

    new_account = CloudAccount(
        organization_id=account_in.organization_id,
        owner_id=current_user.id,
        credentials=credentials
    )
    db.add(new_account)
    db.commit()
    db.refresh(new_account)
    return map_cloud_account(new_account)


@router.get("/", response_model=List[CloudAccountOut])
def list_cloud_accounts(
    organization_id: int = Query(...),
    db: Session = Depends(get_db),
    #current_user: User = Depends(get_current_user)
):
    org = db.query(Organization).filter(
        Organization.id == organization_id,
        Organization.deleted_at.is_(None)
    ).first()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    accounts = db.query(CloudAccount).filter(
        CloudAccount.organization_id == organization_id,
        CloudAccount.deleted_at.is_(None)
    ).all()

    return [map_cloud_account(acc) for acc in accounts]
