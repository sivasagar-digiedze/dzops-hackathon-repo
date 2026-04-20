
# app_init.py
from .workflow.graph import build_graph
from .local_llm import MistralLocalLLM, AzureOpenAILLM

KEY = ""
END_POINT = ""


class AgentContext:
    def __init__(self, llm, db_session):
        self.llm = llm
        self.db_session = db_session

def initialize_agent(db_session):
    print('initialize agent (Azure OpenAI)')

    llm = AzureOpenAILLM(
        api_key = KEY,
        azure_endpoint = END_POINT,
        #deployment_name = "gpt-4.1",
    )

    context = AgentContext(llm, db_session)
    graph = build_graph(context)

    print(context, graph)
    return context, graph

# def initialize_agent(db_session):
#     print('intialize agent')
#     base_url="http://litellm:4000"
#     llm = MistralLocalLLM(base_url = base_url)
#     context = AgentContext(llm, db_session)
#     graph = build_graph(context)
#     print(context, graph)
#     return context, graph

def start_workflow(data, graph):
    print('workflow', data)
    result = graph.invoke(data)
    return result
