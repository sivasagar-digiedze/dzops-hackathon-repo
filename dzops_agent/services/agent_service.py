import ollama
import json
from sqlalchemy.orm import Session
from models.user_models import CloudConnection, Organization
from models.ticket_models import Ticket, CloudResourceCache
from smtp_responder import send_user_reply
from services.tool_registry import TOOL_REGISTRY
import services.tool_providers  # Triggers decorators


class AgentService:
    def __init__(self, db: Session):
        self.db = db


    def search_org_cloud_cache(self, org_id: int, resource_type: str) -> str:
        cache_record = self.db.query(CloudResourceCache).filter_by(
            organization_id=org_id, 
            resource_type=resource_type
        ).first()
        
        if not cache_record:
            return f"No cached data found for {resource_type}. It may not be synced yet."
        return f"Cached {resource_type} State (Synced at {cache_record.last_synced}):\n{cache_record.details_json}"

    def trigger_agent_resolution(self, ticket_id: int, org_id: int, model: str = "llama3.1"):
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket or ticket.status != "Open":
            return False

        print(f"[Agent Service] Resolving Ticket #{ticket.id} [{ticket.subject}] via {model}...\n")
        
        def local_cache_search(resource_type: str):
            return self.search_org_cloud_cache(org_id, resource_type)
            
        def request_info_from_user(question_to_user: str):
            user_email = ticket.user.email
            send_user_reply(ticket.id, user_email, ticket.subject, question_to_user)
            return "Message sent successfully. Awaiting user response."
            
        available_functions = {
            "search_org_cache": local_cache_search,
            "reply_to_user": request_info_from_user
        }
        
        all_tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_org_cache",
                    "description": "Fetch Azure resources from local cache. Use 'VirtualMachine'.",
                    "parameters": {"type": "object", "properties": {"resource_type": {"type": "string"}}, "required": ["resource_type"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "reply_to_user",
                    "description": "Email user to ask for missing details (e.g. specific VM name).",
                    "parameters": {"type": "object", "properties": {"question_to_user": {"type": "string"}}, "required": ["question_to_user"]}
                }
            }
        ]

        # ---- DYNAMIC TOOL INJECTION PHASE ----
        conn = self.db.query(CloudConnection).filter(CloudConnection.organization_id == org_id).first()
        if conn and conn.provider in TOOL_REGISTRY:
            provider_classes = TOOL_REGISTRY[conn.provider]
            for ProviderClass in provider_classes:
                try:
                    tool_instance = ProviderClass(conn)
                    all_tools.extend(tool_instance.get_schemas())
                    available_functions.update(tool_instance.get_callables())
                except Exception as e:
                    print(f"⚠️ [Tool Registry] Failed to load provider {ProviderClass.__name__}: {e}")
        # --------------------------------------

        system_prompt = (
            "You are an Operations Support Agent restricted to actions on Azure.\n"
            "ALWAYS check the local cache using `search_org_cache` before advising.\n"
            "DO NOT guess parameters. Use `reply_to_user` tool to request missing info."
        )

        history = json.loads(ticket.messages_json)
        messages = [{"role": "system", "content": system_prompt}] + history
        
        paused = False
        
        for step in range(3):
            try:
                response = ollama.chat(model=model, messages=messages, tools=all_tools)
            except Exception as e:
                print(f"❌ [Agent Service] Error: {e}")
                break

            message = response['message']
            messages.append(message)
            history.append(message)

            if 'tool_calls' in message and message['tool_calls']:
                for tool_call in message['tool_calls']:
                    function_name = tool_call['function']['name']
                    arguments = tool_call['function']['arguments']
                    result = str(available_functions[function_name](**arguments)) if function_name in available_functions else "Tool unavailable."
                    
                    tool_msg = {"role": "tool", "content": result, "name": function_name}
                    messages.append(tool_msg)
                    history.append(tool_msg)
                    
                    if function_name == "reply_to_user":
                        paused = True
                        break
                
                if paused:
                    ticket.status = "Waiting for Customer"
                    break
            else:
                send_user_reply(ticket.id, ticket.user.email, ticket.subject, message['content'])
                ticket.status = "Resolved"
                break

        ticket.messages_json = json.dumps(history)
        self.db.commit()
        return True
