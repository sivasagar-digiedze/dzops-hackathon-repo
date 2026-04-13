
import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from .database import Base


class CloudResourceCache(Base):
    __tablename__ = 'cloud_resource_cache'
    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    resource_type = Column(String, nullable=False)
    details_json = Column(String, nullable=False)
    last_synced = Column(DateTime, default=datetime.datetime.utcnow)


class Ticket(Base):
    __tablename__ = 'tickets'
    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    subject = Column(String, nullable=False)
    description = Column(String, nullable=False)
    status = Column(String, default="Open")
    messages_json = Column(String, default="[]") 
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    organization = relationship('Organization', back_populates='tickets')
    user = relationship('User', back_populates='tickets')
