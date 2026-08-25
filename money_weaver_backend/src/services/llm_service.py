import json
import os

from src.models.api_key import ApiKey
from src.services.providers import OpenRouterProvider, NvidiaNimProvider
from src.services.providers.registry import ModelRegistry, registry as _registry
from src.services.script_parsing_service import script_parsing_service

ASSIGNMENT_TASKS = ("idea", "script", "enhance", "voice_tts", "video_gen")
DEFAULT_VIDEO_GEN_FALLBACK = "fal-ai/wan-t2v-v2.2"


def resolve_model_for(user_id, task):
    """assignment -> ModelPreference.defaults[task] -> sensible default."""
    if task not in ASSIGNMENT_TASKS:
        raise ValueError(f"unknown assignment task: {task}")
    if user_id:
        try:
            from src.models.model_assignment import ModelAssignment
            from src.models.model_preference import ModelPreference
            from fastapi_app.db import db_session
            with db_session() as session:
                row = session.query(ModelAssignment).filter_by(
                    user_id=user_id, task=task).first()
                if row is not None and row.model_id:
                    return row.model_id
                pref = session.query(ModelPreference).filter_by(user_id=user_id).first()
                if pref is not None and pref.defaults:
                    val = (json.loads(pref.defaults) or {}).get(task)
                    if val:
                        return val
        except Exception as e:
            print(f"resolve_model_for({task}) lookup failed: {e}")
    # Defaults (no user, or nothing stored)
    if task == "voice_tts":
        return "auto"
    if task == "video_gen":
        if os.getenv('COMFY_ENABLED', 'false').lower() != 'true':
            return DEFAULT_VIDEO_GEN_FALLBACK
        return "comfy_local"
    from src.services.providers.registry import PREFERRED_FREE_MODELS
    return _registry.best_free() or PREFERRED_FREE_MODELS[0]


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
            try:
                # Plain session (works in FastAPI request AND Celery context);
                # ApiKey.query would require a Flask app context.
                from fastapi_app.db import db_session
                from src.services.key_encryption import decrypt_key
                with db_session() as session:
                    key = session.query(ApiKey).filter_by(
                        user_id=user_id, provider=provider, is_active=True).first()
                    if key and key.key:
                        return decrypt_key(key.key)
            except Exception as e:
                print(f"api_key_for lookup failed for {provider}: {e}")
        env_names = {"openrouter": "OPENROUTER_API_KEY", "nvidia": "NVIDIA_API_KEY",
                     "fal": "FAL_KEY"}
        env = os.getenv(env_names[provider]) if provider in env_names else None
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

    def _chat_free_resilient(self, user_id, model, messages, **kwargs):
        """Chat with fallback across known-good free models when the primary
        is rate-limited/unavailable (free tiers flap). Non-openrouter models
        and explicit non-fallback failures propagate as before."""
        from src.services.providers.base import ProviderError
        from src.services.providers.registry import PREFERRED_FREE_MODELS
        try:
            return self._chat(user_id, model, messages, **kwargs)
        except ProviderError as e:
            transient = any(code in str(e) for code in ("429", "404", "502", "503"))
            if not transient or not str(model).endswith(":free"):
                raise
        tried = {str(model)}
        for candidate in PREFERRED_FREE_MODELS:
            if candidate in tried:
                continue
            tried.add(candidate)
            try:
                return self._chat(user_id, candidate, messages, **kwargs)
            except ProviderError as e:
                if not any(code in str(e) for code in ("429", "404", "502", "503")):
                    raise
                continue
        raise RuntimeError(f"all free models exhausted; last error: {e}")

    def generate_idea(self, seed=None, model=None, language="en", user_id=None):
        topic = seed if seed else "a surprising and original topic"
        prompt = ("Suggest one random, engaging short-video topic. "
                  "Return strict JSON with keys: title, topic, script. "
                  "The script must use screenplay format (SCENE headings, ACTION lines, "
                  "a NARRATOR character, and DIALOGUE lines). "
                  f"Base it loosely on: {topic}")
        messages = [{"role": "user", "content": prompt}]
        model = model or _registry.best_free() or "nvidia/nemotron-3.5-lightning:free"
        raw = self._chat_free_resilient(user_id, model, messages, temperature=1.1, max_tokens=1500)
        data = self._extract_json(raw)
        if data is not None:
            return {"title": data.get("title", "Untitled"),
                    "topic": data.get("topic", ""),
                    "script": data.get("script", raw)}
        # Reasoning models may prepend CoT; strip <think> blocks and retry.
        import re
        cleaned = re.sub(r"<think>.*?</think>", "", str(raw), flags=re.DOTALL).strip()
        data = self._extract_json(cleaned)
        if data is not None:
            return {"title": data.get("title", "Untitled"),
                    "topic": data.get("topic", ""),
                    "script": data.get("script", cleaned)}
        return {"title": "Untitled", "topic": "", "script": raw}

    @staticmethod
    def _extract_json(text):
        """Pull the first JSON object out of a model response (tolerates
        surrounding prose/code fences). Returns None when nothing parses."""
        if not text:
            return None
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass
        start = str(text).find("{")
        while start != -1:
            decoder = json.JSONDecoder()
            try:
                obj, _ = decoder.raw_decode(str(text)[start:])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
            start = str(text).find("{", start + 1)
        return None

    def generate_script(self, prompt, user_id, model=None, duration=30, niche_id=None):
        if niche_id:
            try:
                from src.services.providers.niche_profile import load, inject_prompt

                niche = load(niche_id)
                prompt = inject_prompt(prompt, niche)
            except FileNotFoundError:
                pass
        try:
            model = model or _registry.best_free() or "nvidia/nemotron-3.5-lightning:free"
            full_prompt = SCREENPLAY_PROMPT.format(seconds=duration, topic=prompt)
            messages = [{"role": "user", "content": full_prompt}]
            return self._chat_free_resilient(user_id, model, messages, max_tokens=2000, temperature=0.7)
        except Exception as e:
            print(f"Error generating script: {e}")
            return (f"SCENE 1: Main\n[ACTION: generic establishing shot]\nNARRATOR\n"
                    f"DIALOGUE: This is a generated script about {prompt}.\nEND")


llm_service = LLMService()
llm_service.build_registry()
