
from sqlalchemy.orm import Session
from models.user_models import User, Organization
import uuid


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def register_user(self, email: str, organization_id: int, role: str = "User") -> User:
        """Handles registering a user and mapping them to their Org."""
        # Simple fake hash for MVP
        faux_hash = str(uuid.uuid4())
        
        user = User(
            email=email,
            password_hash=faux_hash,
            organization_id=organization_id,
            role=role
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
        
    def get_user_by_email(self, email: str) -> User:
        return self.db.query(User).filter(User.email == email).first()
