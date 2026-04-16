import json
import redis
from database import SessionLocal
from models.ticket import Ticket

print("🚀 Worker module loaded", flush=True)

redis_client = redis.Redis(host="aura_redis", port=6379, db=0, decode_responses=True)

QUEUE_NAME = "ticket_queue"


def process_ticket(data, db):
    ticket_id = data.get("ticket_id")

    print(f"📩 Processing ticket {ticket_id}", flush=True)

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    if not ticket:
        print(f"❌ Ticket {ticket_id} not found", flush=True)
        return

    ticket.extracted_intent = "auto_detected_intent"
    ticket.missing_info = {"needs_followup": False}

    db.commit()

    print(f"✅ Processed ticket {ticket_id}", flush=True)


def worker():
    print("👷 Worker started. Waiting for jobs...", flush=True)

    while True:
        try:
            print("⏳ Waiting on Redis queue...", flush=True)

            _, task = redis_client.blpop(QUEUE_NAME, timeout=5)

            if task is None:
                print("🔁 No jobs yet...", flush=True)
                continue

            print(f"📦 Received task: {task}", flush=True)

            payload = json.loads(task)

            db = SessionLocal()

            try:
                if payload.get("task") == "process_ticket":
                    process_ticket(payload.get("data"), db)

            except Exception as e:
                db.rollback()
                print(f"❌ Error processing task: {e}", flush=True)

            finally:
                db.close()

        except Exception as e:
            print(f"🔥 Worker loop error: {e}", flush=True)


if __name__ == "__main__":
    worker()
