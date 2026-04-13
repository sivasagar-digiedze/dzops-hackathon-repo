

from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
import os

class AzureVMManager:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, subscription_id: str = None):
        """
        Initialize the AzureVMManager using specific Service Principal credentials 
        derived from the multi-tenant database for an organization.
        """
        self.subscription_id = subscription_id or os.environ.get("AZURE_SUBSCRIPTION_ID")
        if not self.subscription_id:
            raise ValueError("No subscription ID provided. Set AZURE_SUBSCRIPTION_ID env var.")
        
        # Authenticate specifically for this tenant
        self.credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        self.compute_client = ComputeManagementClient(self.credential, self.subscription_id)

    def get_vm_status(self, resource_group_name: str, vm_name: str) -> str:
        """
        Gets the power state and status of an Azure Virtual Machine.
        """
        try:
            status = self.compute_client.virtual_machines.instance_view(resource_group_name, vm_name)
            statuses = [s.display_status for s in status.statuses]
            return f"VM '{vm_name}' status: {', '.join(statuses)}"
        except Exception as e:
            return f"Error fetching status for VM '{vm_name}': {str(e)}"

    def start_vm(self, resource_group_name: str, vm_name: str) -> str:
        """
        Starts an Azure Virtual Machine.
        """
        try:
            # begin_start returns a poller object. We will just start and wait.
            poller = self.compute_client.virtual_machines.begin_start(resource_group_name, vm_name)
            poller.result()  # Wait for completion
            return f"VM '{vm_name}' has been started successfully."
        except Exception as e:
            return f"Error starting VM '{vm_name}': {str(e)}"

    def stop_vm(self, resource_group_name: str, vm_name: str) -> str:
        """
        Stops and deallocates an Azure Virtual Machine.
        """
        try:
            poller = self.compute_client.virtual_machines.begin_deallocate(resource_group_name, vm_name)
            poller.result()
            return f"VM '{vm_name}' has been stopped and deallocated successfully."
        except Exception as e:
            return f"Error stopping VM '{vm_name}': {str(e)}"

# Define the structured specifications for Ollama tool calling natively
azure_vm_tools_specs = [
    {
        "type": "function",
        "function": {
            "name": "get_vm_status",
            "description": "Get the current running status and power state of an Azure Virtual Machine",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource_group_name": {
                        "type": "string",
                        "description": "The name of the Azure Resource Group."
                    },
                    "vm_name": {
                        "type": "string",
                        "description": "The name of the Azure Virtual Machine."
                    }
                },
                "required": ["resource_group_name", "vm_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "start_vm",
            "description": "Start an existing Azure Virtual Machine",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource_group_name": {
                        "type": "string",
                        "description": "The name of the Azure Resource Group."
                    },
                    "vm_name": {
                        "type": "string",
                        "description": "The name of the Azure Virtual Machine."
                    }
                },
                "required": ["resource_group_name", "vm_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stop_vm",
            "description": "Stop and deallocate an Azure Virtual Machine",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource_group_name": {
                        "type": "string",
                        "description": "The name of the Azure Resource Group."
                    },
                    "vm_name": {
                        "type": "string",
                        "description": "The name of the Azure Virtual Machine."
                    }
                },
                "required": ["resource_group_name", "vm_name"]
            }
        }
    }
]
