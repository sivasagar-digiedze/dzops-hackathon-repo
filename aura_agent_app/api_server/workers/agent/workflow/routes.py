
# routers.py

def route_after_validation(state):
    if state.get("needs_clarification"):
        return "clarification_email"
    return "provider_resolver"


def route_after_provider(state):
    if state.get("needs_clarification"):
        return "clarification_email"
    return "credentials"


def route_after_credentials(state):
    resource = (state.get("resource") or "").lower()

    if "storage" in resource:
        return "azure_storage"

    return "basic"
