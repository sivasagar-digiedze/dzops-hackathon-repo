
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import redis
import json
from schemas.ticket import InboundEmailWebhook
from models.organization import Organization
from models.ticket import Ticket
from database import get_db
from models.ticket import Ticket
from database import get_db

router = APIRouter()

redis_client = redis.Redis(host="aura_redis", port=6379, db=0, decode_responses=True)

QUEUE_NAME = "ticket_queue"


@router.post("/gmail")
def receive_email_webhook(
    payload: InboundEmailWebhook,
    db: Session = Depends(get_db)
):
    # 1. Identify organization by support email
    org = db.query(Organization).filter(Organization.customer_email == payload.from_email,
                                        Organization.support_email == payload.to_email).first()
    if not org:
        raise HTTPException(status_code = 404, detail="Organization not found for this support email")

    # 2. Create the ticket
    ticket = Ticket(
        organization_id = org.id,
        sender_email = payload.from_email, #customer email
        subject = payload.subject, 
        body = payload.text_body,
        thread_id = payload.message_id
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    task_info = {
        "organization_id": org.id,
        "ticket_id": ticket.id,
        "owner_email": org.owner_email,
        "customer_email": org.customer_email,
        "email_meta": {
            "thread_id": ticket.thread_id,
            "subject": ticket.subject,
            "body": ticket.body
        }
    }
    
    redis_payload = {
        "task": "process_ticket",
        "data": task_info
    }
    redis_client.rpush(QUEUE_NAME, json.dumps(redis_payload))
    return {
        "message": "Ticket created & queued",
        "ticket_id": ticket.id
    }
