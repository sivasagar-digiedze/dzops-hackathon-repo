
# app_init.py
from .workflow.graph import build_graph
from .local_llm import MistralLocalLLM


class AgentContext:
    def __init__(self, llm):
        self.llm = llm

def initialize_agent():
    llm = MistralLocalLLM(base_url="http://0.0.0.0:4000")
    context = AgentContext(llm)
    graph = build_graph(context)
    return context, graph

def start_workflow(data, graph):
    initial_state = {
        "message": data["message"],
        "customer_email": data["customer_email"],
        "thread_id": data.get("thread_id"),
        "cloud_meta": data["cloud_account_meta"],
    }

    result = graph.invoke(initial_state)
    return result
