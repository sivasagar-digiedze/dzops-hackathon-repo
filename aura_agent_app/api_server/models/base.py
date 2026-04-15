import time
from sqlalchemy import Column, Integer
from sqlalchemy.orm import declarative_base

Base = declarative_base()

def utc_now():
    return int(time.time())

class BaseMixin:
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(
        Integer,
        nullable=False,
        default=utc_now
    )

    deleted_at = Column(
        Integer,
        nullable=True,
        default=None   # ✅ important change
    )

    def soft_delete(self):
        self.deleted_at = utc_now()
