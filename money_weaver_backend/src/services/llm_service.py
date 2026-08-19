import json
import os

from src.models.api_key import ApiKey
from src.services.providers import OpenRouterProvider, NvidiaNimProvider
from src.services.providers.registry import ModelRegistry, registry as _registry
from src.services.script_parsing_service import script_parsing_service

SCREENPLAY_PROMPT = """You are a documentary screenwriter. Write a full screenplay for a
{seconds}-second video about: {topic}

Use standard screenplay format. Each scene block must look EXACTLY like this:

SCENE 1: [Short scene name]
[ACTION: one visual action line describing the shot]
NARRATOR
[DIALOGUE: the narration sentence(s) to be spoken]

End the screenplay with a line "END".

Return the screenplay only, no commentary."""


class LLMService:
    def __init__(self):
        self.providers = []

    def build_registry(self, providers=None):
        if providers is not None:
            self.providers = providers
        else:
            self.providers = [OpenRouterProvider(), NvidiaNimProvider()]
        _registry.providers = self.providers
        _registry._cache = None
        return _registry

    def api_key_for(self, user_id, provider):
        if user_id:
            key = ApiKey.query.filter_by(user_id=user_id, provider=provider, is_active=True).first()
            if key and key.key:
                return key.key
        env = os.getenv("OPENROUTER_API_KEY") if provider == "openrouter" else os.getenv("NVIDIA_API_KEY")
        return env

    def pick_model(self, user_id, prefs, task):
        return _registry.resolve(prefs, task)

    def _provider_for(self, model):
        return _registry.provider_for(model) or _registry.providers[0] if _registry.providers else None

    def _chat(self, user_id, model, messages, **kwargs):
        p = self._provider_for(model)
        if p is None:
            raise RuntimeError("no provider configured")
        p.api_key = self.api_key_for(user_id, p.name)
        return p.chat(model, messages, **kwargs)

    def generate_idea(self, seed=None, model=None, language="en"):
        topic = seed if seed else "a surprising and original topic"
        prompt = ("Suggest one random, engaging short-video topic. "
                  "Return strict JSON with keys: title, topic, script. "
                  "The script must use screenplay format (SCENE headings, ACTION lines, "
                  "a NARRATOR character, and DIALOGUE lines). "
                  f"Base it loosely on: {topic}")
        messages = [{"role": "user", "content": prompt}]
        model = model or _registry.best_free() or "openrouter/free"
        raw = self._chat(None, model, messages, temperature=1.1, max_tokens=1500)
        try:
            data = json.loads(raw)
            return {"title": data.get("title", "Untitled"),
                    "topic": data.get("topic", ""),
                    "script": data.get("script", raw)}
        except json.JSONDecodeError:
            return {"title": "Untitled", "topic": "", "script": raw}

    def generate_script(self, prompt, user_id, model=None, duration=30):
        try:
            model = model or _registry.best_free() or "openrouter/free"
            full_prompt = SCREENPLAY_PROMPT.format(seconds=duration, topic=prompt)
            messages = [{"role": "user", "content": full_prompt}]
            return self._chat(user_id, model, messages, max_tokens=2000, temperature=0.7)
        except Exception as e:
            print(f"Error generating script: {e}")
            return (f"SCENE 1: Main\n[ACTION: generic establishing shot]\nNARRATOR\n"
                    f"DIALOGUE: This is a generated script about {prompt}.\nEND")


llm_service = LLMService()
llm_service.build_registry()
