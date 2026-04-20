
from langchain.tools import tool
import json
from .utils import extract_json, send_smtp_email
from .prompts import BASE_SYSTEM, ROUTER_PROMPT, CLARIFY_PROMPT, PARAMS_EXTRACTOR_PROMPT, CONVERSATION_SUMMARISATION_PROMPT
from .azure_clients import AzureClient
from models.agent_state import AgentMessage, AgentWorkFlow
from azure.core.exceptions import AzureError, ResourceNotFoundError, ResourceExistsError


def create_tools(context):

############################################
#basic tools

    @tool
    def approval_parser(message: str):
        """
        Parses a user's natural language input to determine if they have 
        granted or denied approval for a proposed action.

        Args:
            message (str): The raw text response from the user (e.g., "Yes, go ahead").

        Returns:
            dict: A dictionary containing the approval status. 
                Returns {"approved": True} for positive confirmation, or 
                {"approved": False, "rejected": True} for negative responses.
                Returns None if the intent is ambiguous.
        """
        positive = ["yes", "approve", "go ahead", "confirm"]
        negative = ["no", "cancel", "stop"]
        msg = message.lower()
        if any(p in msg for p in positive):
            return {"approved": True}
        if any(n in msg for n in negative):
            return {"approved": False, "rejected": True}

    @tool
    def intent_router(message: str):
        """
        Analyzes the user's message to classify it into specific cloud operation metadata.
        
        This tool uses an LLM to determine the intent, target resource, specific action, 
        and whether the request falls within the supported cloud operations scope.

        Args:
            message (str): The raw user input string to be classified.

        Returns:
            dict: A classification object containing:
                - intent (str): A brief label of the user's goal.
                - resource (str): The target entity (e.g., 'storage_account', 'vm').
                - action (str): The operation type (e.g., 'create', 'list').
                - cloud_provider (str/null): The identified provider (e.g., 'azure').
                - is_cloud_op (bool): Whether the request is a cloud infrastructure task.
                - is_out_of_scope (bool): Whether the request is off-topic or a greeting.

        Raises:
            ValueError: If the LLM response is not valid JSON or misses required keys.
        """
        prompt = ROUTER_PROMPT.format(base = BASE_SYSTEM, message = message)
        resp = context.llm.generate(prompt)
        if hasattr(resp, "content"):
            resp = resp.content
        response_json = extract_json(resp)
        if not response_json:
            raise ValueError(f"Router invalid output: {resp}")
        data = json.loads(response_json)
        for k in ["intent", "resource", "action", "cloud_provider", "is_cloud_op"]:
            if k not in data:
                raise ValueError(f"Missing key: {k}")
        return data


    @tool
    def credentials(cloud_meta: dict, provider: str):
        """
        Retrieves matching cloud credentials and account details from the metadata.

        Args:
            cloud_meta (dict): Dictionary containing preloaded account information.
            provider (str): The cloud provider to filter by (e.g., 'azure', 'aws').

        Returns:
            dict: The specific credential and account data if a single match is found,
                  or a list of options if multiple accounts exist for the provider.

        Raises:
            ValueError: If no accounts match the specified provider.
        """

        accounts = cloud_meta.get("accounts", [])
        matched = [a for a in accounts if a["cloud_type"] == provider]
        if not matched:
            raise ValueError(f"No account for provider: {provider}")
        if len(matched) == 1:
            print("#.... credentials node")
            return {
                "credentials": matched[0]["credentials"],
                "cloud_account": matched[0]
            }
        return {
            "multiple_accounts": True,
            "accounts": matched
        }

    @tool
    def generate_clarification_email(message: str, missing_fields: list):
        """
        Drafts a concise email to the customer requesting missing information.

        Args:
            message (str): The original user request.
            missing_fields (list): The specific data points needed (e.g., ['region', 'sku']).

        Returns:
            str: The generated email body text.
        """

        prompt = CLARIFY_PROMPT.format(
            base=BASE_SYSTEM,
            message=message,
            missing_fields=missing_fields
        )

        resp = context.llm.generate(prompt)
        if hasattr(resp, "content"):
            resp = resp.content
        return resp.strip()


    @tool
    def send_email_to_customer(customer_email: str, body: str):
        """
        Dispatches an email to the specified recipient via SMTP.

        Args:
            customer_email (str): The recipient's email address.
            body (str): The content of the email to be sent.
        """

        send_smtp_email(customer_email, "Clarification Required", body)


    @tool
    def basic_tool(thread_id, customer_email, message: str):
        """
        Provides a graceful fallback response for out-of-scope or unidentifiable requests.
        """

        body = f"""
                Hi,

                Thanks for reaching out!

                I'm Aura, your cloud operations assistant. I help manage and automate tasks across your cloud resources (like storage accounts, blobs, and infrastructure operations).

                It looks like I couldn't clearly map your request below to a supported cloud action:

                "{message}"

                Here are a few examples of what you can ask me:
                • Create or manage Azure storage accounts  
                • Upload, download, or list blobs  
                • Retrieve configuration details of cloud resources  

                If you had something specific in mind, feel free to reply with more details—I'll be happy to assist!

                Best regards,  
                Aura Agent
                """

        send_smtp_email(customer_email, "Need more details to assist you", body,
                        thread_id = thread_id)



    @tool
    def param_extractor(message: str, resource: str, action: str):
        """
        Parses the user message to extract specific technical parameters required for Azure operations.

        Args:
            message (str): The user's natural language input.
            resource (str): The target Azure resource (e.g., 'storage_account').
            action (str): The operation being performed (e.g., 'create').

        Returns:
            dict: A collection of identified parameters (e.g., {'location': 'eastus', 'sku': 'Standard_LRS'}).
        """

        prompt = PARAMS_EXTRACTOR_PROMPT.format(
            resource = resource,
            action = action,
            message = message
        )
        resp = context.llm.generate(prompt)
        print("RAW PARAM EXTRACTOR RESPONSE:", resp)
        if hasattr(resp, "content"):
            resp = resp.content
        data = extract_json(resp)
        return data if isinstance(data, dict) else {}
    
    @tool
    def save_message(organization_id, thread_id, sender, message):
        """
        Persists a single chat message to the database for conversation history tracking.

        Args:
            thread_id (str): Unique identifier for the current chat session.
            sender (str): The author of the message ('user' or 'agent').
            message (str): The text content to be saved.
        """

        message_obj = AgentMessage(
            organization_id = organization_id,
            thread_id = thread_id,
            sender = sender,
            message = message
        )
        context.db_session.add(message_obj)
        context.db_session.commit()
        context.db_session.refresh(message_obj)

    
    @tool
    def get_conversation_messages(thread_id: str):
        """
        Retrieves the chronological history of messages for a specific conversation thread.

        Args:
            thread_id (str): Unique identifier for the chat session.

        Returns:
            list[dict]: A list of message objects containing 'sender' and 'message' keys.
        """

        records = context.db_session.query(AgentMessage).filter(
            AgentMessage.thread_id == thread_id
        ).order_by(AgentMessage.id.asc()).all()
        return  [
        {"sender": r.sender, "message": r.message}
        for r in records
        ]
    
    @tool
    def conversation_summarizer(messages: list):
        """
        Compresses the recent chat history into a structured execution context using an LLM.

        Args:
            messages (list): A list of message dictionaries from the conversation history.

        Returns:
            dict: A summarized state object containing key decisions, extracted values, and pending items.
        """
        convo = []
        for m in messages:
            role = "User" if m["sender"] == "user" else "Agent"
            convo.append(f"{role}: {m['message']}")

        conversation_text = "\n".join(convo[-10:])
        resp = context.llm.generate(CONVERSATION_SUMMARISATION_PROMPT.format(
            conversation_text = conversation_text))
        if hasattr(resp, "content"):
            resp = resp.content
        data = extract_json(resp)
        return json.loads(data) if data else {}

    
    @tool
    def save_workflow(thread_id: str, state: dict, status: str):
        """
        Saves the current operational state and progress of a cloud workflow to the database.

        Args:
            thread_id (str): Unique identifier for the chat session.
            state (dict): The current JSON-serializable state of the agent's workflow.
            status (str): The lifecycle stage of the workflow (e.g., 'pending', 'completed').
        """

        agent_state_obj = AgentWorkFlow(
            ticket_id = state['ticket_id'],
            organization_id = state['organization_id'],
            thread_id = thread_id,
            state_json = state,
            status = status
        )
        context.db_session.add(agent_state_obj)
        context.db_session.commit()
        context.db_session.refresh(agent_state_obj)

    @tool
    def load_workflow(thread_id: str, organization_id):
        """
        Fetches the most recent workflow state for a given thread and organization.

        Args:
            thread_id (str): Unique identifier for the chat session.
            organization_id (str): The ID of the organization owning the workflow.

        Returns:
            dict|None: The last saved state dictionary, or None if no record exists.
        """

        record = context.db_session.query(AgentWorkFlow).filter(
            AgentWorkFlow.thread_id == thread_id,
            AgentWorkFlow.organization_id == organization_id
        ).order_by(AgentWorkFlow.id.desc()).first()
        return record.state_json if record else None



    @tool
    def send_success_email(customer_email: str, action: str, result: dict | list, message_id: str = None):
        """
        Sends a customer-friendly success email based on action outcome.
        """

        # 🧠 Build dynamic message based on action
        if action in ["list", "describe"]:
            resource_list = "\n".join([f"• {name}" for name in result])

            body = f"""
                    Hi,

                    Thanks for reaching out!

                    Here are the storage accounts available in your subscription:

                    {resource_list}

                    If you’d like more details about any specific storage account, just let me know—I’ll be happy to help.

                    Best regards,  
                    Aura Agent
                    """

        elif action == "create":
                    body = f"""
            Hi,

            Your request has been successfully completed ✅

            Here are the details of the newly created Azure Storage Account:

            • Name: {result.get("name")}
            • Location: {result.get("primary_location")}
            • Resource ID: {result.get("id")}
            • Status: {result.get("status")}

            If you need help with further configurations (like containers, access policies, or uploads), feel free to reply.

            Best regards,  
            Aura Agent
            """

        else:
                    body = f"""
            Hi,

            Your request was processed successfully.

            Result:
            {result}

            Let me know if you need anything else.

            Best regards,  
            Aura Agent
            """

        send_smtp_email(
            receiver_email=customer_email,
            subject="Re: Update on your Azure request",
            body=body,
            thread_id=message_id
        )
################################################################
# Azure Cloud Tools
    
    @tool
    def execute_blob_crud(client, action, params):
        """
        Performs data-plane operations on Azure Blob Storage.
        
        Supported Actions:
        - 'list': Returns list of container names (default) or blob names if 'container_name' provided.
        - 'upload': Uploads data to a specific blob. Requires 'container_name', 'blob_name', and 'data'.
        - 'delete': Deletes a specific blob. Requires 'container_name' and 'blob_name'.
        """
        try:
            if action == "list":
                if params.get("container_name"):
                    container = client.get_container_client(params["container_name"])
                    return [b.name for b in container.list_blobs()]
                return [c.name for c in client.list_containers()]

            elif action == "read":
                container = client.get_container_client(params["container_name"])
                return [b.name for b in container.list_blobs()]

            elif action == "upload":
                container = client.get_container_client(params["container_name"])
                blob = container.get_blob_client(params["blob_name"])
                blob.upload_blob(params["data"], overwrite=True)
                return f"Successfully uploaded {params['blob_name']} to {params['container_name']}."

            elif action == "delete":
                container = client.get_container_client(params["container_name"])
                blob = container.get_blob_client(params["blob_name"])
                blob.delete_blob()
                return f"Successfully deleted blob {params['blob_name']}."
            
            raise ValueError(f"Action '{action}' is not supported for Blob CRUD.")
        
        except ResourceNotFoundError:
            return "Error: The specified container or blob was not found."
        except ResourceExistsError:
            return "Error: The resource already exists."
        except AzureError as e:
            return f"Azure Operation Failed: {e.message}"

    
    @tool
    def execute_storage_account(client, action, params):
        """
        Performs control-plane operations for Azure Storage Account management.
        
        Supported Actions:
        - 'list': Lists names of all storage accounts in the subscription.
        - 'create': Provisions a new StorageV2 account. Requires 'resource_group', 'account_name', 'location', and 'sku'.
        """
        try:
         
            if action in ["list", "describe"]:
                return [a.name for a in client.storage_accounts.list()]

            elif action == "create":
                poller = client.storage_accounts.begin_create(
                    params.get("resource_group"),
                    params.get("account_name"),
                    {
                    "location": params.get("location"),
                    "sku": {"name": params.get("sku")},
                    "kind": "StorageV2"}
                    )
                result = poller.result()
                return {
                    "status": "Created",
                    "name": result.name,
                    "id": result.id,
                    "primary_location": result.primary_location
                }
            raise ValueError(f"Action '{action}' is not supported for Storage Account management.")
        except AzureError as e:
            return f"Azure Management Error: {e.message}"

    return {
        "save_message":save_message,
        "get_conversation_messages": get_conversation_messages,
        "conversation_summarizer": conversation_summarizer,
        "save_workflow": save_workflow,
        "load_workflow": load_workflow,
        "intent_router": intent_router,
        "credentials": credentials,
        "generate_clarification_email": generate_clarification_email,
        "send_email_to_customer": send_email_to_customer,
        "basic_tool": basic_tool,
        "approval_parser": approval_parser,
        "send_success_email": send_success_email,

        "azure_client_factory": AzureClient,
        "param_extractor": param_extractor,
        "blob_dispatcher": execute_blob_crud,
        "execute_storage_account": execute_storage_account,
    }
