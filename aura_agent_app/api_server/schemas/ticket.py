from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any

class TicketBase(BaseModel):
    sender_email: EmailStr
    subject: Optional[str] = None
    body: str

class TicketCreate(TicketBase):
    org_id: int
    thread_id: Optional[str] = None

class TicketOut(TicketBase):
    id: int
    org_id: int
    status: str
    extracted_intent: Optional[str] = None
    missing_info: Optional[Dict[str, Any]] = None
    thread_id: Optional[str] = None

    class Config:
        from_attributes = True

class InboundEmailWebhook(BaseModel):
    # This is a sample webhook payload that we might expect from an email service like SendGrid, Mailgun, or a custom Gmail pubsub processor
    to_email: EmailStr
    from_email: EmailStr # sender (customer)
    subject: str
    text_body: str
    message_id: str # Can be used as thread ID
