
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
import re
import json
from models.database import get_db
from models.user_models import User
from models.ticket_models import Ticket
from services.agent_service import AgentService

router = APIRouter(prefix="/webhook", tags=["Incoming Agent Hooks"])


class EmailPayload(BaseModel):
    sender_email: str
    subject: str
    body: str


def offload_to_agent(ticket_id: int, org_id: int, db: Session):
    service = AgentService(db)
    service.trigger_agent_resolution(ticket_id, org_id)


@router.post("/incoming-email")
def ingest_email_ticket(payload: EmailPayload, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.sender_email).first()
    if not user:
        raise HTTPException(status_code=401, detail=f"Unauthorized: unregistered organization.")

    org_id = user.organization_id
    ticket_id = None
    
    # Thread tracking
    thread_match = re.search(r"\[Ticket #(\d+)\]", payload.subject, re.IGNORECASE)
    if thread_match:
        ticket_id = int(thread_match.group(1))
        existing_ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org_id).first()
        
        if existing_ticket:
            messages = json.loads(existing_ticket.messages_json)
            messages.append({"role": "user", "content": payload.body})
            existing_ticket.messages_json = json.dumps(messages)
            existing_ticket.status = "Open"
            db.commit()
            print(f"[Webhook Agent] Appended reply to existing Ticket #{ticket_id}")
        else:
            ticket_id = None
            
    if not ticket_id:
        initial_messages = [{"role": "user", "content": payload.body}]
        new_ticket = Ticket(
            organization_id=org_id,
            user_id=user.id,
            subject=payload.subject,
            description=payload.body,
            messages_json=json.dumps(initial_messages)
        )
        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)
        ticket_id = new_ticket.id
        print(f"[Webhook Agent] Ingested New Ticket #{ticket_id} for Org {org_id}")
    
    background_tasks.add_task(offload_to_agent, ticket_id, org_id, db)
    return {"status": "Accepted", "ticket_id": ticket_id, "organization": org_id, "message": "Resolution Triggered"}
