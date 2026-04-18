
import requests
from langchain_core.language_models.llms import LLM

class MistralLocalLLM(LLM):
    base_url: str

    @property
    def _llm_type(self):
        return "mistral-local"

    def _call(self, prompt, stop = None, **kwargs):
        res = requests.post(
            f"{self.base_url}/v1/completions",
            json={
                "model": "mistral-local",
                "prompt": prompt,
                "max_tokens": 500,
                "temperature": 0
            }
        )
        data = res.json()
        output = data.get("content")
        if not output:
            raise ValueError(f"Empty LLM response: {data}")
        return output.strip()
