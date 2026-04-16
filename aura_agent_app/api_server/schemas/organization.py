from pydantic import BaseModel, EmailStr
from typing import List, Optional

class OrganizationBase(BaseModel):
    name: str
    support_email: EmailStr
    customer_email: EmailStr
    owner_email: EmailStr

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationOut(OrganizationBase):
    id: int

    class Config:
        from_attributes = True

class CloudAccountBase(BaseModel):
    organization_id: int
    tenant_id: str
    client_id: str
    subscription_id: str

class CloudAccountCreate(CloudAccountBase):
    client_secret: str # Plaintext in request, encrypted in DB

class CloudAccountOut(CloudAccountBase):
    id: int
    organization_id: int
    owner_id: int

    tenant_id: str
    client_id: str
    subscription_id: str

    class Config:
        from_attributes = True
