
from typing import TypedDict, Optional, Dict, List

class AgentState(TypedDict):

    #preloaded meta info 
    ticket_id: int
    message: str
    cloud_account_meta: Optional[Dict]
    owner_email: str
    customer_email: str
    thread_id: str

    #intent node
    intent: Optional[str]
    resource: Optional[str]
    action: Optional[str]
    cloud_provider: Optional[str]
    is_cloud_op: Optional[bool]

    #flow control
    needs_clarification: bool
    missing_fields: List[str]
    available_providers: List[str]

    #execution
    credentials: Dict
    cloud_account: Dict
    result: str
    error: str
