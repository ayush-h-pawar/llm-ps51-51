"""HTTP adapters; no patient text or API keys are written to logs."""
import requests
from core import ReportError

class LLMClient:
    def __init__(self, provider, model, api_key="", base_url="http://127.0.0.1:8080"):
        self.provider, self.model = provider, model.strip()
        self.api_key, self.base_url = api_key.strip(), base_url.rstrip("/")
        if not self.model:
            raise ReportError("Enter a model name.")
        if provider == "Groq" and not self.api_key:
            raise ReportError("Enter a Groq API key in the sidebar or set GROQ_API_KEY.")

    def complete(self, system, user):
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        headers = {"Content-Type": "application/json"}
        if self.provider == "Ollama":
            url = self.base_url + "/api/chat"
            body = {"model": self.model, "messages": messages, "stream": False, "format": "json", "options": {"temperature": 0, "num_predict": 2200, "num_ctx": 8192}}
        else:
            url = "https://api.groq.com/openai/v1/chat/completions" if self.provider == "Groq" else self.base_url + "/v1/chat/completions"
            if self.provider == "Groq":
                headers["Authorization"] = "Bearer " + self.api_key
            body = {"model": self.model, "messages": messages, "temperature": 0, "max_tokens": 2200, "response_format": {"type": "json_object"}}
        try:
            response = requests.post(url, json=body, headers=headers, timeout=(10, 240))
            response.raise_for_status()
            payload = response.json()
            result = payload["message"]["content"] if self.provider == "Ollama" else payload["choices"][0]["message"]["content"]
            if not isinstance(result, str):
                raise ValueError("Response is not text")
            return result
        except requests.Timeout as exc:
            raise ReportError("The model timed out. Try a shorter report or check the local server.") from exc
        except requests.HTTPError as exc:
            code = exc.response.status_code
            detail = {401: "API key rejected", 403: "access denied", 404: "model or endpoint not found", 429: "rate limit reached"}.get(code, "provider request failed")
            raise ReportError(f"Model error {code}: {detail}. Check configuration and try again.") from exc
        except requests.RequestException as exc:
            raise ReportError("Cannot reach the model. Start the local server or check your connection.") from exc
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ReportError("The provider returned an unexpected response format.") from exc
