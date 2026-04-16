from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from typing import List
from schemas.organization import OrganizationCreate, OrganizationOut
from models.organization import Organization
from models.user import User
from database import get_db
from routes.auth import get_current_user

router = APIRouter()

@router.post("/", response_model=OrganizationOut)
def create_organization(
    org_in: OrganizationCreate, 
    db: Session = Depends(get_db),
    #current_user: User = Depends(get_current_user)
):
    #need to add a table such that the organization can contain multiple users
    new_org = Organization(name = org_in.name, support_email=org_in.support_email,
                           customer_email=org_in.customer_email, owner_email=org_in.owner_email)
    db.add(new_org)
    db.commit()
    db.refresh(new_org)
    return new_org

@router.get("/", response_model=List[OrganizationOut])
def list_organizations(
    db: Session = Depends(get_db),
    #current_user: User = Depends(get_current_user)
):
    organizations = db.query(Organization).all()
    return organizations

@router.get("/{id}", response_model=OrganizationOut)
def get_organization_by_id(id: int = Path(..., description="Organization ID"),
    db: Session = Depends(get_db),
    #current_user: User = Depends(get_current_user)
):
    organization = db.query(Organization).filter(
        Organization.id == id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization
