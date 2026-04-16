
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from models.base import Base, BaseMixin

class Organization(BaseMixin, Base):
    __tablename__ = "organizations"

    name = Column(String, unique=True, index=True, nullable=False)
    support_email = Column(String, nullable=False)
    customer_email = Column(String, nullable=False)
    owner_email = Column(String, nullable=False)
    
    cloud_accounts = relationship("CloudAccount", back_populates="organization")
    tickets = relationship("Ticket", back_populates="organization")
