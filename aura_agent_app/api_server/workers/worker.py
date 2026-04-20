
import json
import redis
from database import SessionLocal
from workers.agent.main import start_workflow, initialize_agent

print("🚀 Worker module loaded", flush=True)

redis_client = redis.Redis(host="aura_redis", port=6379, db=0, decode_responses=True)


QUEUE_NAME = "ticket_queue"


def process_ticket(data, db, graph):
    ticket_id = data.get("ticket_id")
    print(f"Processing ticket {ticket_id}", flush=True)
    org_id = data.get('organization_id')
    ca_dict = {
        "organization_id": org_id,
        "cloud_type": "azure",
        "credentials":{
        "tenant_id": "",
        "client_id": "",
        "subscription_id": "",
        "client_secret" : "",
        },
        "id": 1,
        "owner_id": 2
    }
    accounts_list = [ca_dict]
    workflow_payload = {
        "ticket_id": ticket_id,
        "organization_id" : org_id,
        "customer_email" : data.get('customer_email'),
        "owner_email": data.get('owner_email'),
        "thread_id": data.get('email_meta', {}).get('thread_id', None),
        "message" : data.get('email_meta', {}).get('body', ''),
    }
    workflow_payload['cloud_account_meta'] = {"accounts": accounts_list}

    start_workflow(workflow_payload, graph)


def worker():
    print("Worker started. Waiting for jobs...", flush=True)
    db = SessionLocal()
    context, graph = initialize_agent(db) 
    while True:
        try:
            print("Waiting on Redis queue...", flush=True)
            _, task = redis_client.blpop(QUEUE_NAME, timeout=5)
            if task is None:
                print("No jobs yet...", flush=True)
                continue
            print(f"Received task: {task}", flush=True)
            payload = json.loads(task)
            try:
                if payload.get("task") == "process_ticket":
                    process_ticket(payload.get("data"), db, graph)
            except Exception as e:
                db.rollback()
                print(f"Error processing task: {e}", flush=True)
            finally:
                db.close()
        except Exception as e:
            print(f"Worker loop error: {e}", flush=True)


if __name__ == "__main__":
    worker()
