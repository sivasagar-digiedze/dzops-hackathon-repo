
from .state import AgentState
from models.cloud_account import CloudAccount

# 1
def intent_node(tools):
    def node(state: AgentState):
        result = tools["intent_router"].invoke({
            "message": state["message"]
        })

        return {**state, **result}
    return node

# 2) Validation node
def validation_node(state: AgentState):
    missing = []
    if not state.get("is_cloud_op"):
        return {**state, "needs_clarification": False}
    if state.get("resource") in [None, "unknown"]:
        missing.append("resource")
    if state.get("action") in [None, "unknown"]:
        missing.append("action")
    if missing:
        return {
            **state,
            "needs_clarification": True,
            "missing_fields": missing
        }
    return {**state, "needs_clarification": False}

# 3 
def cloud_provider_resolver_node():
    def node(state: AgentState):
        if not state.get("is_cloud_op"):
            return state
        if state.get("cloud_provider"):
            return {**state, "needs_clarification": False}
        ca_accounts = state.get("cloud_account_meta", {}).get("accounts", [])
        providers = list(set([a["cloud_type"] for a in ca_accounts]))
        if len(providers) == 0:
            return {
                **state,
                "error": "No cloud accounts found"
            }
        if len(providers) == 1:
            return {
                **state,
                "cloud_provider": providers[0],
                "needs_clarification": False
            }
        return {
            **state,
            "available_providers": providers,
            "needs_clarification": True,
            "missing_fields": ["cloud_provider"]
        }
    return node

# 4) Clarification email node
def clarification_email_node(tools):
    def node(state: AgentState):

        body = tools["generate_clarification_email"].invoke({
            "message": state["message"],
            "missing_fields": state.get("missing_fields", [])
        })

        tools["send_email_to_customer"].invoke({
            "customer_email": state["customer_email"],
            "body": body
        })

        return {
            **state,
            "result": "Waiting for user response"
        }

    return node

# 5
def credentials_node(tools):
    def node(state: AgentState):

        result = tools["credentials"].invoke({
            "cloud_meta": state["cloud_account_meta"],
            "provider": state["cloud_provider"]
        })
        return {
            **state,
            **result
        }
    return node


def azure_storage_node(tools):
    def node(state):
        result = tools["azure_storage_tool"].invoke({
            "credentials": state["credentials"],
            "action": state["action"]
        })
        return {
            **state,
            "result": result
        }
    return node

def basic_node(tools):
    def node(state):

        result = tools["basic_tool"].invoke({
            "message": state["message"]
        })

        return {
            **state,
            "result": result
        }

    return node
