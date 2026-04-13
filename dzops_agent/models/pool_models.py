from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class Pool(Base):
    __tablename__ = 'pools'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    organization = relationship('Organization', back_populates='pools')
    owner = relationship('User', back_populates='managed_pools')
    resources = relationship('PoolResource', back_populates='pool', cascade="all, delete-orphan")

class PoolResource(Base):
    __tablename__ = 'pool_resources'
    id = Column(Integer, primary_key=True, autoincrement=True)
    pool_id = Column(Integer, ForeignKey('pools.id'), nullable=False)
    resource_type = Column(String, nullable=False) # e.g. VirtualMachine
    resource_identifier = Column(String, nullable=False) # e.g. VM Name or Azure ID
    
    pool = relationship('Pool', back_populates='resources')
