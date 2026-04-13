
from sqlalchemy.orm import Session
from models.pool_models import Pool, PoolResource


class PoolService:
    def __init__(self, db: Session):
        self.db = db

    def create_pool(self, name: str, org_id: int, owner_id: int) -> Pool:
        pool = Pool(name=name, organization_id=org_id, owner_id=owner_id)
        self.db.add(pool)
        self.db.commit()
        self.db.refresh(pool)
        return pool

    def add_resource_to_pool(self, pool_id: int, resource_type: str, identifier: str) -> PoolResource:
        res = PoolResource(
            pool_id=pool_id, 
            resource_type=resource_type, 
            resource_identifier=identifier
        )
        self.db.add(res)
        self.db.commit()
        self.db.refresh(res)
        return res

    def get_user_pools(self, user_id: int):
        return self.db.query(Pool).filter(Pool.owner_id == user_id).all()
