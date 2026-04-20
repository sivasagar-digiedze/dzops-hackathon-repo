
from .state import AgentState
from .utils import RESOURCE_CONTRACTS, build_conversation_context


#1
def resume_node(tools):
    print("#1 Resume Node")

    def node(state: AgentState):

        tools["save_message"].invoke({
            "organization_id": state["organization_id"],
            "thread_id": state["thread_id"],
            "sender": "user",
            "message": state["message"]
            })
        
        #check the message is already processed or not
        existing_state = tools["load_workflow"].invoke({
            "thread_id": state["thread_id"],
            "organization_id": state["organization_id"]
        })
        if not existing_state:
            print("*** First message - fresh flow")

            return {
                **state,
                "params": {},
                "approved": False,
                "awaiting_approval": False,
                "awaiting_clarification": False
            }

        #Approval Flow  
        if existing_state.get("status") == "waiting_approval":
            approval = tools["approval_parser"].invoke({
                "message": state["message"]
            })
            return {
                **existing_state,
                "approved": approval.get("approved", False),
                "awaiting_approval": False,
                "message": state["message"]
            }


        #if exists, get the conversation messages history and summarise it
        messages = tools["get_conversation_messages"].invoke({
            "thread_id": state["thread_id"]
        })
        summary = tools["conversation_summarizer"].invoke({
            "messages": messages
        }) or {}

        result = {
                **existing_state,
                "message": summary.get("last_user_message", state["message"]),
                "params": {
                    **existing_state.get("params", {}),
                    **summary.get("params", {})
                },
                "intent": summary.get("intent") or existing_state.get("intent"),
                "resource": summary.get("resource") or existing_state.get("resource"),
                "action": summary.get("action") or existing_state.get("action"),
                "awaiting_clarification": False,
                "awaiting_approval": False
            }
        print(f"*** #1 Resume Node: {result}")
        return result

    return node

################################################################    

# 2
def intent_node(tools):
    print("#2 intent_node")

    def node(state: AgentState):

        #Skip if already resolved
        if state.get("intent") and state.get("resource"):
            return state

        #First message
        message = state.get("message", "")

        #history
        messages_history = tools["get_conversation_messages"].invoke({
            "thread_id": state["thread_id"]
            })
        if not messages_history or len(messages_history) == 1:
            # first message → no need for history
            context = message
        else:
            # multi-turn → build context
            context = build_conversation_context(messages_history)
        
        result = tools["intent_router"].invoke({
            "message": context
        })
        params = tools["param_extractor"].invoke({
            "message": context,
            "resource": result.get("resource"),
            "action": result.get("action")
        })
        result = {**state, **result, "params" : params}
        print(f"*** #2 Intent Node: {result}")
        return result

    return node

#3 Validation node
def validation_node(state: AgentState):
    print(f"#3 validation_node")

    result = {**state, "needs_clarification": False}

    if not state.get("is_cloud_op"):
        return result
    
    resource = state.get("resource")
    action = state.get("action")
    params = state.get("params", {})

    contract = RESOURCE_CONTRACTS.get(resource, {}).get(action, [])
    missing = [field for field in contract if not params.get(field)]

    if missing:
        result = {
            **state,
            "needs_clarification": True,
            "missing_fields": missing
        }
    print(f"*** #3 validation_node: {result}")

    return result

# 4 
def cloud_provider_resolver_node():
    print("#4 cloud_provider_resolver_node")
    def node(state: AgentState):
        result = {**state, "needs_clarification": False}

        if not state.get("is_cloud_op"):
            print("#4 cloud_provider_resolver_node result-112", state)
            return state
        
        if state.get("cloud_provider"):
            print("#4 cloud_provider_resolver_node result-116", result)
            return result

        ca_accounts = state.get("cloud_account_meta", {}).get("accounts", [])
        providers = list(set([a["cloud_type"] for a in ca_accounts if a.get("cloud_type")]))

        if not providers:
            result = {
                **state,
                "error": "No cloud accounts found",
                "status": "failed"
            }
            print("#4 cloud_provider_resolver_node result-128", result)
            return result
 
        if len(providers) == 1:
            result = {
                **state,
                "cloud_provider": providers[0],
                "needs_clarification": False
            }
            print("#4 cloud_provider_resolver_node result-136", result)
            return result
        
        result = {
            **state,
            "available_providers": providers,
            "needs_clarification": True,
            "missing_fields": ["cloud_provider"],
            "status": "waiting_clarification"
        }
        print("#4 cloud_provider_resolver_node result-145", result)
        return result

    return node

# 5) Clarification email node
def clarification_email_node(tools):
    print(f"#5 clarification_email_node")

    def node(state: AgentState):

        body = tools["generate_clarification_email"].invoke({
            "message": state["message"],
            "missing_fields": state.get("missing_fields", [])
        })

        tools["save_message"].invoke({
            "thread_id": state["thread_id"],
            "sender": "agent",
            "message": body
        })

        tools["send_email_to_customer"].invoke({
            "customer_email": state["customer_email"],
            "body": body
        })

        tools["save_workflow"].invoke({
            "thread_id": state["thread_id"],
            "state": state,
            "status": "waiting_clarification"
        })
        result = {**state, "awaiting_clarification": True,}
        print(f"#5 clarification_email_node result", result)

        return result

    return node

#6 Approval Node
def approval_node(tools):
    print("#6 Approval Node")

    def node(state: AgentState):

        body = f"""
                Approval required for the requested operation:

                Action: {state['action']}
                Resource: {state['resource']}
                Details: {state.get('params')}

                Please reply with YES to approve or NO to cancel.

                Happy to help,  
                Aura Agent
                """
        tools["save_message"].invoke({
            "thread_id": state["thread_id"],
            "sender": "agent",
            "message": body
        })

        tools["send_email_to_customer"].invoke({
            "customer_email": state["owner_email"],
            "body": body
            })
        
        tools["save_workflow"].invoke({
            "thread_id": state["thread_id"],
            "state": state,
            "status": "waiting_approval"
        })

        result = {
            **state,
            "awaiting_approval": True,
            "status": "waiting_approval"
        }
        print("#6 Approval Node Result", result)

        return result
        
    return node


# 7
def credentials_node(tools):
    print("#7 Credentials Node")

    def node(state: AgentState):

        if not state.get("cloud_provider"):
            return {
                **state,
                "error": "Missing cloud provider",
                "status": "failed"
            }

        result = tools["credentials"].invoke({
            "cloud_meta": state["cloud_account_meta"],
            "provider": state["cloud_provider"]
        })
        if result.get("multiple_accounts"):
            node_result = {
                **state,
                "needs_clarification": True,
                "missing_fields": ["cloud_account"],
                "available_accounts": result["accounts"],
                "status": "waiting_clarification"
            }
            print("#7 Credentials Node result", node_result)
            return node_result
        
        node_result = {
            **state,
            **result
        }
        print("#7 Credentials Node result", node_result)

        return node_result
    
    return node


#5 Azure Storage Node
def azure_storage_node(tools):
    print(f"*** #5 azure_storage_node")

    def node(state):
        try:
            azure = tools["azure_client_factory"](state["credentials"])

            client = azure.get_resource_client(
                "storage",
                account_name=state["params"].get("account_name")
            )

            result = tools["blob_dispatcher"](
                client=client,
                action=state["action"],
                params=state["params"]
            )

            tools["save_workflow"].invoke({
                "thread_id": state["thread_id"],
                "state": state,
                "status": "completed"
            })

            result = {
                **state,
                "result": result,
                "error": None
            }
            print(f"*** #5 azure_storage_node result", result)
            return result

        except Exception as e:
            tools["send_email_to_customer"].invoke({
                "customer_email": state["customer_email"],
                "body": f"""
                            We encountered an issue while processing your request.
                            Error: {str(e)}
                            Please verify the details and let me know how you'd like to proceed.
                            Happy to help,  
                            Aura Agent
                        """
                })
            return {
                **state,
                "error": str(e),
                "result": "Execution failed"
                }     
    return node


#6 Azure Storage Account Node
def azure_storage_account_node(tools):
    print("#6 azure storage account node")

    def node(state: AgentState):
        try:
            azure = tools["azure_client_factory"](state["credentials"])
            client = azure.get_resource_client("storage_account")

            result = tools["execute_storage_account"].invoke({
                "client" : client,
                "action":state["action"],
                "params":state["params"]
            }
            )

            if state["action"] in ["list", "describe"]:
                email_body = "\n".join(result) if result else "No storage accounts found."
            else:
                email_body = str(result)

            result = {
                    **state,
                    "result": result,
                    "error": None
                }
            
            print("#6 azure storage account node result", result)
            tools["send_success_email"].invoke({
                "customer_email": state["customer_email"],
                "action": state["action"],
                "result": email_body,
                "message_id": state["thread_id"]
            })
            return result
            
        except Exception as e:
            tools["send_email_to_customer"].invoke({
                "customer_email": state["customer_email"],
                "body": f"""
                            We encountered an issue while processing your request.
                            Error: {str(e)}
                            Please verify the details and let me know how you'd like to proceed.
                            Happy to help,  
                            Aura Agent
                        """
                })
            return {
                **state,
                "error": str(e),
                "result": "Execution failed"
                }    
 
    return node


def basic_node(tools):
    def node(state):

        result = tools["basic_tool"].invoke({
            "thread_id": state["thread_id"],
            "customer_email": state["customer_email"],
            "message": state["message"]
        })

        return {
            **state,
            "result": result
        }

    return node
