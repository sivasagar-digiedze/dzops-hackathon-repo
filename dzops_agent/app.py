
import uvicorn
from fastapi import FastAPI
from models.database import Base, engine
from api import (routes_auth, routes_organization, routes_pool, routes_webhook,
                routes_notifications, routes_tickets, routes_audit)

# Re-Initialize the strictly decoupled Data Models
Base.metadata.create_all(bind=engine)

app = FastAPI(title="DZOps Multi-Tenant Agent Server")


# Register cleanly segregated API routes
app.include_router(routes_auth.router)
app.include_router(routes_organization.router)
app.include_router(routes_pool.router)
app.include_router(routes_webhook.router)
app.include_router(routes_notifications.router)
app.include_router(routes_tickets.router)
app.include_router(routes_audit.router)


@app.get("/")
def health_check():
    return {"status": "DZOps Agent Operational - SOLID Architecture"}


if __name__ == "__main__":
    print("🚀 DZOps API Server starting cleanly...")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
