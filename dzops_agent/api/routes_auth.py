
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from models.database import get_db
from services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["Authentication"])

class RegisterRequest(BaseModel):
    email: str
    organization_id: int
    role: str = "User"


@router.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    service = UserService(db)
    if service.get_user_by_email(request.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = service.register_user(request.email, request.organization_id, request.role)
    return {"message": "User registered", "user_id": user.id, "email": user.email}
