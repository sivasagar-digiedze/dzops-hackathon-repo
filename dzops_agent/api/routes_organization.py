
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from models.database import get_db
from services.org_service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["Organization"])

class OrgCreateRequest(BaseModel):
    name: str

class CloudConnectionRequest(BaseModel):
    tenant_id: str
    client_id: str
    client_secret: str


@router.post("/")
def create_organization(request: OrgCreateRequest, db: Session = Depends(get_db)):
    service = OrganizationService(db)
    org = service.create_organization(request.name)
    return {"message": "Organization created", "org_id": org.id, "name": org.name}


@router.post("/{org_id}/cloud-connection")
def add_cloud_connection(org_id: int, request: CloudConnectionRequest, db: Session = Depends(get_db)):
    service = OrganizationService(db)
    conn = service.register_cloud_connection(org_id, request.tenant_id, request.client_id, request.client_secret)
    return {"message": "Cloud connection registered securely", "connection_id": conn.id}
