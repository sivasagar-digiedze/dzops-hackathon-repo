
from sqlalchemy import Column, Integer, String, ForeignKey, Text, JSON, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from models.base import Base, BaseMixin


class AgentWorkFlow(BaseMixin, Base):
    __tablename__ = "agent_workflow"

    ticket_id = Column(Integer, nullable=False)
    organization_id = Column(Integer, nullable = False)
    thread_id = Column(String, nullable = True)
    state_json = Column(JSON, nullable = True)
    status = Column(String, nullable = True)

class AgentMessage(BaseMixin, Base):
    __tablename__ = "agent_messages"

    id = Column(Integer, primary_key=True)

    thread_id = Column(String, index=True)
    organization_id = Column(Integer, nullable=False)

    sender = Column(String)  # "user" | "agent"
    message = Column(Text)
