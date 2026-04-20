
from sqlalchemy import Column, Integer, String
from models.base import Base, BaseMixin
from sqlalchemy.orm import relationship

class User(BaseMixin, Base):
    __tablename__ = "users"

    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    name = Column(String, nullable=False)

    cloud_accounts = relationship("CloudAccount", back_populates="owner")
