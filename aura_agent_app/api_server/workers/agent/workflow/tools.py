

from langchain.tools import tool
import json
from .utils import extract_json, send_smtp_email
from .prompts import BASE_SYSTEM, ROUTER_PROMPT, CLARIFY_PROMPT

def create_tools(context):

    # 1) LLM Router (single call)
    @tool
    def intent_router(message: str):
        """Classify user request into intent/resource/action/provider/is_cloud_op"""

        prompt = ROUTER_PROMPT.format(base = BASE_SYSTEM, message = message)

        resp = context.llm.invoke(prompt)
        if hasattr(resp, "content"):
            resp = resp.content
        response_json = extract_json(resp)
        if not j:
            raise ValueError(f"Router invalid output: {resp}")
        data = json.loads(response_json)
        # strict validation
        for k in ["intent", "resource", "action", "cloud_provider", "is_cloud_op"]:
            if k not in data:
                raise ValueError(f"Missing key: {k}")

        return data

    # 2) Credentials (state-driven)
    @tool
    def credentials(cloud_meta: dict, provider: str):
        """Select credentials from preloaded cloud_meta"""
        accounts = cloud_meta.get("accounts", [])
        matched = [a for a in accounts if a["cloud_type"] == provider]
        if not matched:
            raise ValueError(f"No account for provider: {provider}")
        if len(matched) == 1:
            return {
                "credentials": matched[0]["credentials"],
                "cloud_account": matched[0]
            }
        return {
            "multiple_accounts": True,
            "accounts": matched
        }

    # 3) Clarification email generator
    @tool
    def generate_clarification_email(message: str, missing_fields: list):
        """Generate short clarification email"""

        prompt = CLARIFY_PROMPT.format(
            base=BASE_SYSTEM,
            message=message,
            missing_fields=missing_fields
        )

        resp = context.llm.invoke(prompt)
        if hasattr(resp, "content"):
            resp = resp.content
        return resp.strip()

    # 4) Email sender
    @tool
    def send_email_to_customer(customer_email: str, body: str):
        """Send email"""
        send_smtp_email(customer_email, "Clarification Required", body)

    # 5) Basic fallback
    @tool
    def basic_tool(message: str):
        return f"I couldn't map this to a cloud operation: {message}"

    # 6) Example resource tool
    @tool
    def azure_storage_tool(credentials: dict, action: str):
        return f"Executed {action} on Azure Storage"

    return {
        "intent_router": intent_router,
        "credentials": credentials,
        "generate_clarification_email": generate_clarification_email,
        "send_email_to_customer": send_email_to_customer,
        "basic_tool": basic_tool,
        "azure_storage_tool": azure_storage_tool,
    }
