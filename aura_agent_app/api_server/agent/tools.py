from langchain_core.tools import tool
from typing import Optional, Dict, Any

# These tools would normally initialize the Azure SDK using credentials
# passed down from the cloud account associated with the ticket.
# We will use simple mock implementations with type hints that the LLM can use.

@tool
def get_azure_resource_groups(subscription_id: str) -> list[str]:
    """Retrieve all Azure Resource Groups for a given subscription."""
    # Mock return
    return ["rg-prod-eastus", "rg-dev-eastus"]

@tool
def create_azure_vm(
    resource_group: str, 
    vm_name: str, 
    vm_size: str = "Standard_DS1_v2", 
    image: str = "UbuntuLTS"
) -> str:
    """Create a new Virtual Machine in Azure."""
    # Azure SDK logic to create VM using azure-mgmt-compute
    return f"Successfully queued creation of VM {vm_name} in {resource_group} with size {vm_size}."

@tool
def check_missing_parameters(intent: str, extracted_params: Dict[str, Any]) -> str:
    """
    Evaluates if we have all needed information for an Azure intent.
    If yes, returns 'COMPLETE'.
    If no, returns a list of missing parameters asked back to the user.
    """
    required_map = {
        "CREATE_VM": ["resource_group", "vm_name"],
        "CREATE_STORAGE": ["storage_account_name", "location"]
    }
    
    if intent not in required_map:
        return "UNKNOWN_INTENT"
        
    reqs = required_map[intent]
    missing = [r for r in reqs if r not in extracted_params or not extracted_params[r]]
    
    if missing:
        return f"MISSING: {', '.join(missing)}"
    return "COMPLETE"

# List of tools to bind to the LLM
azure_tools = [get_azure_resource_groups, create_azure_vm, check_missing_parameters]
