
from sqlalchemy.orm import Session
from models.user_models import Organization, CloudConnection


class OrganizationService:
    def __init__(self, db: Session):
        self.db = db

    def create_organization(self, name: str) -> Organization:
        org = Organization(name=name)
        self.db.add(org)
        self.db.commit()
        self.db.refresh(org)
        return org

    def register_cloud_connection(self, org_id: int, tenant_id: str, client_id: str, client_secret: str):
        # In a real environment, encrypt client_secret here
        conn = CloudConnection(
            organization_id=org_id,
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret_encrypted=client_secret 
        )
        self.db.add(conn)
        self.db.commit()
        self.db.refresh(conn)
        return conn
