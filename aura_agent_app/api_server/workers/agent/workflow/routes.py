
# routers.py

def route_after_validation(state):

    if state.get("needs_clarification"):
        return "clarification_email"
    
    if state.get("action") in ["delete", "update"]:
        if not state.get("approved"):
            return "approval"
        
    return "provider_resolver"


def route_after_provider(state):
    if not state.get("is_cloud_op"):
        return "basic" 
    
    if state.get("error"):
        return "basic"
    
    if state.get("needs_clarification"):
        return "clarification_email"

    return "credentials"

def route_after_credentials(state):
    if state.get("error"):
        return "basic"
    
    resource = (state.get("resource") or "").lower()
    print("*******************", resource)

    if resource == "storage":
        return "azure_storage"

    if resource == "storage_account":
        return "azure_storage_account"

    return "basic"
