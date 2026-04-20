
from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient
from azure.mgmt.storage import StorageManagementClient


class AzureClient:

    def __init__(self, credentials):
        self.credentials = credentials
        self.subscription_id = self.credentials['subscription_id']
        self._azure_client = None
    
    @property
    def azure_client(self):
        if self._azure_client is None:
            self._azure_client = ClientSecretCredential(
                tenant_id = self.credentials["tenant_id"],
                client_id = self.credentials["client_id"],
                client_secret = self.credentials["client_secret"]
                )
        return self._azure_client
    
    def get_resource_client(self, resource: str, **kwargs):

        credential = self.azure_client
        if resource == "storage":
            account_name = kwargs.get("account_name")
            if not account_name:
                raise ValueError("account_name is required for storage operations")
            return BlobServiceClient(account_url=f"https://{account_name}.blob.core.windows.net",
                                     credential = credential)

        elif resource == "storage_account":
            return StorageManagementClient(
                credential,
                self.subscription_id
            )

        raise ValueError(f"Unsupported resource: {resource}")
