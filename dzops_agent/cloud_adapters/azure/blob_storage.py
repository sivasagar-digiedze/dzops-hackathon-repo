

from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient
import os


class AzureBlobManager:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, account_url: str = None):
        """
        Initialize the AzureBlobManager using tenant-specific credentials.
        """
        self.account_url = account_url or os.environ.get("AZURE_STORAGE_ACCOUNT_URL")
        if not self.account_url:
            raise ValueError("No Storage Account URL provided. Set AZURE_STORAGE_ACCOUNT_URL env var (e.g. https://<account>.blob.core.windows.net).")
        
        # Authenticate with specific tenant keys
        self.credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        self.blob_service_client = BlobServiceClient(account_url=self.account_url, credential=self.credential)

    def list_containers(self) -> str:
        """
        Lists all containers in the Azure Storage Account.
        """
        try:
            containers = self.blob_service_client.list_containers()
            container_names = [c.name for c in containers]
            if not container_names:
                return "No containers found in the storage account."
            return f"Containers found: {', '.join(container_names)}"
        except Exception as e:
            return f"Error listing containers: {str(e)}"

    def list_blobs(self, container_name: str) -> str:
        """
        Lists blobs in a specific container.
        """
        try:
            container_client = self.blob_service_client.get_container_client(container_name)
            blobs = container_client.list_blobs()
            blob_names = [b.name for b in blobs]
            if not blob_names:
                return f"No blobs found in container '{container_name}'."
            # Limiting to 50 blobs to prevent huge outputs
            resp = f"Blobs in '{container_name}': {', '.join(blob_names[:50])}"
            if len(blob_names) > 50:
                resp += f" ...and {len(blob_names) - 50} more."
            return resp
        except Exception as e:
            return f"Error listing blobs in container '{container_name}': {str(e)}"


# Define structured specifications for Ollama tool calling natively
azure_blob_tools_specs = [
    {
        "type": "function",
        "function": {
            "name": "list_containers",
            "description": "Lists all containers within the configured Azure Storage Account.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_blobs",
            "description": "Lists files or blobs within a specific Azure Blob Storage container.",
            "parameters": {
                "type": "object",
                "properties": {
                    "container_name": {
                        "type": "string",
                        "description": "The name of the Azure Blob Storage container."
                    }
                },
                "required": ["container_name"]
            }
        }
    }
]
