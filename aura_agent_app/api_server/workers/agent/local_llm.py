
import requests
from langchain_core.language_models.llms import LLM
import requests

class MistralLocalLLM(LLM):
    base_url: str

    @property
    def _llm_type(self):
        return "phi-local"

    def _call(self, prompt, stop = None, **kwargs):
        res = requests.post(
            f"{self.base_url}/v1/completions",
            json={
                "model": "phi-local",
                "prompt": prompt,
                "max_tokens": 1000,
                "temperature": 0
            }
        )
        data = res.json()
        output = data.get("content")
        if not output:
            raise ValueError(f"Empty LLM response: {data}")
        return output.strip()


class AzureOpenAILLM:

    def __init__(self, api_key, azure_endpoint, model="gpt-4.1"):
        """
        azure_endpoint example:
        https://<resource>.services.ai.azure.com/api/projects/<project>/openai/v1/responses
        """
        self.api_key = api_key
        self.url = azure_endpoint
        self.model = model

    @property
    def _llm_type(self):
        return "azure-openai"

    def generate(self, prompt: str) -> str:
        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key
        }

        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt
                        }
                    ]
                }
            ],
            "temperature": 0
        }

        res = requests.post(self.url, headers=headers, json=payload)

        # 🔍 Basic error handling
        if res.status_code != 200:
            raise Exception(f"Request failed: {res.status_code} - {res.text}")

        data = res.json()

        print(data)

        # ✅ Extract response safely
        try:
            return data["output"][0]["content"][0]["text"].strip()
        except Exception:
            raise ValueError(f"Unexpected response format: {data}")
