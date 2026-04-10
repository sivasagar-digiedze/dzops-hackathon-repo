import ollama
import os

os.environ["OLLAMA_HOST"] = "http://127.0.0.1:11434"

def llm_tool(prompt):
    response = ollama.chat(
        model='llama3',
        messages=[{'role': 'user', 'content': prompt}]
    )
    return response['message']['content'].strip()