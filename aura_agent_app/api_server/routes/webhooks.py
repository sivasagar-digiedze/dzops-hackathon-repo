from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage
from schemas.ticket import InboundEmailWebhook
from models.organization import Organization
from models.ticket import Ticket
from database import get_db
from agent.graph import agent_graph
from models.ticket import Ticket
from database import get_db

router = APIRouter()

def process_email_background(ticket_id: int, db: Session):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        db.close()
        return

    ticket.status = "processing"
    db.commit()
    print(f"Background processing started for ticket {ticket_id}")
    
    # Construct the initial state for the agent
    initial_state = {
        "messages": [HumanMessage(content=ticket.body)],
        "ticket_id": ticket.id,
        "intent": "",
        "extracted_params": {},
        "ready_to_execute": False
    }
    
    # Invoke LangGraph agent
    try:
        final_state = agent_graph.invoke(initial_state)
        ticket.status = "processed"
        # We can dump final states or extracted entities to DB here
    except Exception as e:
        print(f"Agent execution failed: {e}")
        ticket.status = "failed"
    
    db.commit()
    db.close()

@router.post("/gmail")
def receive_email_webhook(
    payload: InboundEmailWebhook,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # 1. Identify organization by support email
    org = db.query(Organization).filter(Organization.support_email == payload.to).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found for this support email")
    
    # 2. Create the ticket
    new_ticket = Ticket(
        org_id=org.id,
        sender_email=payload.from_email,
        subject=payload.subject,
        body=payload.text_body,
        thread_id=payload.message_id
    )
    db.add(new_ticket)
    db.commit()
    db.refresh(new_ticket)
    
    # 3. Queue background processing for the AI Agent
    # We pass the ID so the background worker can open its own DB session
    # In a real queued system (like Celery), you'd push to Redis here. 
    # For now, BackgroundTasks is sufficient for an MVP.
    background_tasks.add_task(process_email_background, new_ticket.id, next(get_db()))
    
    return {"status": "received", "ticket_id": new_ticket.id}
