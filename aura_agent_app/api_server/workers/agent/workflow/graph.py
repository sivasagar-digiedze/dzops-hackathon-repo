
# graph.py
from langgraph.graph import StateGraph, END
from .tools import create_tools
from .nodes import (
    intent_node,
    validation_node,
    cloud_provider_resolver_node,
    clarification_email_node,
    credentials_node,
    azure_storage_node,
    basic_node,
    approval_node,
    resume_node,
    azure_storage_account_node,
)
from .routes import (
    route_after_validation,
    route_after_provider,
    route_after_credentials
)
from .state import AgentState

def build_graph(context):

    tools = create_tools(context)
    builder = StateGraph(AgentState)

    print('build graph')

    # nodes
    builder.add_node("resume", resume_node(tools))
    builder.add_node("intent_node", intent_node(tools))
    builder.add_node("validation", validation_node)
    builder.add_node("provider_resolver", cloud_provider_resolver_node())
    builder.add_node("clarification_email", clarification_email_node(tools))
    builder.add_node("approval", approval_node(tools))
    builder.add_node("credentials", credentials_node(tools))
    builder.add_node("azure_storage", azure_storage_node(tools))
    builder.add_node("azure_storage_account", azure_storage_account_node(tools))
    builder.add_node("basic", basic_node(tools))

    builder.set_entry_point("resume")

    #flow
    builder.add_edge("resume", "intent_node")
    builder.add_edge("intent_node", "validation")
    
    builder.add_conditional_edges(
        "validation",
        route_after_validation,
        {
            "clarification_email": "clarification_email",
            "approval": "approval",
            "provider_resolver": "provider_resolver"
        }
    )
    builder.add_conditional_edges(
        "provider_resolver",
        route_after_provider,
        {
            "clarification_email": "clarification_email",
            "credentials": "credentials",
            "basic": "basic"
        }
    )

    builder.add_conditional_edges(
        "credentials",
        route_after_credentials,
        {
            "azure_storage": "azure_storage",
            "azure_storage_account": "azure_storage_account",
            "basic": "basic"
        }
    )

    # end states
    builder.add_edge("clarification_email", END)
    builder.add_edge("approval", END)
    builder.add_edge("azure_storage", END)
    builder.add_edge("azure_storage_account", END)
    builder.add_edge("basic", END)

    return builder.compile()
