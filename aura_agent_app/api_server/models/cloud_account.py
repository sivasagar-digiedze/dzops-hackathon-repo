
from sqlalchemy import Column, Integer, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from models.base import Base, BaseMixin

class CloudAccount(BaseMixin, Base):
    __tablename__ = "cloud_accounts"

    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    credentials = Column(JSON, nullable=False)
    cloud_type = Column(String, nullable = False)
    # Relationships
    organization = relationship("Organization", back_populates="cloud_accounts")
    owner = relationship("User", back_populates="cloud_accounts")
