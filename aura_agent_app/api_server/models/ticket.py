
from sqlalchemy import Column, Integer, String, ForeignKey, Text, JSON, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from models.base import Base, BaseMixin

class Ticket(BaseMixin, Base):
    __tablename__ = "tickets"

    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    sender_email = Column(String, nullable=False)
    subject = Column(String, nullable=True)
    body = Column(Text, nullable=False)
    status = Column(String, default="open", index=True) # open, waiting_info, resolved, closed
    
    # LLM Extracted Data
    extracted_intent = Column(String, nullable=True)
    missing_info = Column(JSON, nullable=True)
    thread_id = Column(String, index=True, nullable=True) # To track email threads or agent runs
    
    # Relationships
    organization = relationship("Organization", back_populates="tickets")

