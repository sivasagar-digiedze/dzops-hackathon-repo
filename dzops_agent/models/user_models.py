from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class Organization(Base):
    __tablename__ = 'organizations'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    
    users = relationship('User', back_populates='organization')
    cloud_connections = relationship('CloudConnection', back_populates='organization')
    tickets = relationship('Ticket', back_populates='organization')
    pools = relationship('Pool', back_populates='organization')


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=True) # Enabled for registration API
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    role = Column(String, default="User")
    
    organization = relationship('Organization', back_populates='users')
    tickets = relationship('Ticket', back_populates='user')
    managed_pools = relationship('Pool', back_populates='owner')


class CloudConnection(Base):
    __tablename__ = 'cloud_connections'
    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    provider = Column(String, default="Azure")
    tenant_id = Column(String, nullable=False)
    client_id = Column(String, nullable=False)
    client_secret_encrypted = Column(String, nullable=False)
    
    organization = relationship('Organization', back_populates='cloud_connections')
