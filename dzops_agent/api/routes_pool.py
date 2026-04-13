
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from models.database import get_db
from services.pool_service import PoolService

router = APIRouter(prefix="/pools", tags=["Resource Pools Governance"])

class PoolCreateRequest(BaseModel):
    name: str
    organization_id: int
    owner_id: int

class PoolResourceRequest(BaseModel):
    resource_type: str # e.g. VirtualMachine
    resource_identifier: str # e.g. vm-backend-01


@router.post("/")
def create_pool(request: PoolCreateRequest, db: Session = Depends(get_db)):
    service = PoolService(db)
    pool = service.create_pool(request.name, request.organization_id, request.owner_id)
    return {"message": "Resource pool created under Governance", "pool_id": pool.id, "name": pool.name}


@router.post("/{pool_id}/resources")
def add_resource_to_pool(pool_id: int, request: PoolResourceRequest, db: Session = Depends(get_db)):
    service = PoolService(db)
    res = service.add_resource_to_pool(pool_id, request.resource_type, request.resource_identifier)
    return {"message": "Resource successfully governed under pool", "pool_name": res.pool.name, "resource": res.resource_identifier}
