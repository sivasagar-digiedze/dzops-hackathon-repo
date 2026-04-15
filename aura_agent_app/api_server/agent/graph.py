from typing import Annotated, TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from agent.tools import azure_tools
from config import settings

print(settings.LLM_API_BASE)
print(settings.LLM_MODEL_NAME)

llm = ChatOpenAI(
    base_url = settings.LLM_API_BASE,
    api_key = "dummy",
    model = settings.LLM_MODEL_NAME,
    temperature = 0
)

print(hasattr(llm, "bind_tools"))

# Bind the tools to the model
llm_with_tools = llm.bind_tools(azure_tools)

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], "The sequence of messages"]
    ticket_id: int
    intent: str
    extracted_params: Dict[str, Any]
    ready_to_execute: bool

def intent_analyzer_node(state: AgentState):
    """Analyzes the user email to determine intent and extract params."""
    messages = state["messages"]
    system_prompt = HumanMessage(content=(
        "You are an Azure CloudOps support agent. "
        "Read the customer email and run check_missing_parameters to evaluate the intent and extracted variables."
    ))
    
    # We pass the history and prompt to the LLM
    response = llm_with_tools.invoke([system_prompt] + messages)
    
    # In a full flow, you would parse the tool calls to update `state['intent']`
    # and `state['extracted_params']`.
    
    return {"messages": messages + [response]}

def execution_node(state: AgentState):
    """Executes the specific Azure tool if ready."""
    messages = state["messages"]
    last_msg = messages[-1]
    
    # This node will parse `last_msg.tool_calls` and run the associated Python `azure_tools`.
    # For now, it simply appends a mock result.
    action_result = AIMessage(content=f"Executed Azure Operation for ticket {state['ticket_id']}.")
    
    return {"messages": messages + [action_result]}

def should_execute(state: AgentState) -> str:
    # A simple router: if the LLM called check_missing_parameters and output was "COMPLETE", we go to execute.
    # Otherwise go to END (which might trigger an email reply back to user)
    last_msg = state['messages'][-1]
    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
        # Check if the tool called is an execution tool (e.g., create_azure_vm)
        for call in last_msg.tool_calls:
            if call['name'] in ["create_azure_vm", "get_azure_resource_groups"]:
                return "execute"
    return "end"

# Build Graph
graph_builder = StateGraph(AgentState)
graph_builder.add_node("analyzer", intent_analyzer_node)
graph_builder.add_node("execution", execution_node)

graph_builder.set_entry_point("analyzer")
graph_builder.add_conditional_edges(
    "analyzer",
    should_execute,
    {
        "execute": "execution",
        "end": END
    }
)
graph_builder.add_edge("execution", END)

# Compile
agent_graph = graph_builder.compile()
