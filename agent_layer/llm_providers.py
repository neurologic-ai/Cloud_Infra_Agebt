import os
import google.generativeai as genai
from openai import OpenAI

class LLMClient:
    """
    Minimal abstraction so you can switch between OpenAI and Google (Gemini).
    Use via: LLMClient().chat(system="...", user="...")
    """
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "openai").lower()
        if self.provider == "google":
            genai.configure(api_key=os.getenv("GOOGLE_API_KEY", ""))
            self.model_name = os.getenv("GOOGLE_MODEL", "gemini-1.5-flash-002")
            self._genai = genai
        else:
            self._openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY", None))
            self.model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def chat(self, system: str, user: str, **kwargs) -> str:
        if self.provider == "google":
            model = self._genai.GenerativeModel(self.model_name, system_instruction=system)
            resp = model.generate_content(user, **kwargs)
            return (getattr(resp, "text", None) or "").strip()
        else:
            resp = self._openai.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                **kwargs
            )
            return (resp.choices[0].message.content or "").strip()
