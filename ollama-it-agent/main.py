
from fastapi import FastAPI
from pydantic import BaseModel
from app import process_ticket

app = FastAPI()


class TicketRequest(BaseModel):
    ticket: str
    step: int = 0


@app.post("/process-ticket")
def process(req: TicketRequest):
    return process_ticket(req.ticket, req.step)
