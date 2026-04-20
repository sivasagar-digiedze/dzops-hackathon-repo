
from typing import TypedDict, Optional, Dict, List

class AgentStateBase(TypedDict):
    # required fields
    ticket_id: int
    organization_id: int
    message: str
    owner_email: str
    customer_email: str
    thread_id: str


class AgentState(AgentStateBase, total=False):
    # optional / evolving fields

    # preloaded meta
    cloud_account_meta: Dict

    # intent node
    intent: Optional[str]
    is_out_of_scope: bool
    resource: Optional[str] = None
    action: Optional[str] = None
    cloud_provider: Optional[str] = None
    is_cloud_op: bool

    # flow control
    needs_clarification: bool
    missing_fields: Optional[List[str]] = []
    available_providers: Optional[List[str]] = []

    # execution
    credentials: Optional[Dict] = None
    cloud_account: Optional[Dict] = None
    result: Optional[str] = None
    error: Optional[str] = None

    params: Optional[Dict] = None
    awaiting_approval: bool
    awaiting_clarification: bool
    last_action: Optional[str] = None
    approved: bool
    status: bool

