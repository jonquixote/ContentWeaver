"""ComfyUI HTTP gateway client.

Thin wrapper around the ComfyUI REST API used by the generative video
pipeline:

- health()          -> bool          GET  {COMFY_URL}/system_stats
- queue_workflow()  -> prompt_id     POST {COMFY_URL}/prompt
- poll_result()     -> {status,...}  GET  {COMFY_URL}/history/{prompt_id}
- get_view()        -> bytes         GET  {COMFY_URL}/view

All network I/O goes through httpx so tests can mock it without any real
traffic. WebSocket progress streaming is intentionally not used; history
polling is sufficient and keeps the dependency surface small.
"""
import asyncio
import copy
import json
import os
import uuid

import httpx

COMFY_URL = os.getenv("COMFY_URL", "http://comfy:8188")

# workflows/ lives at the backend root (two levels above src/services).
_WORKFLOWS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "workflows",
)
DEFAULT_WORKFLOW_FILE = "wan22_t2v_api.json"
PROMPT_PLACEHOLDER = "__PROMPT__"


def health():
    """True when the ComfyUI server answers /system_stats with HTTP 200."""
    try:
        return httpx.get(f"{COMFY_URL}/system_stats", timeout=2).status_code == 200
    except Exception:
        return False


async def queue_workflow(workflow: dict, client_id: str = None):
    """Submit an API-format workflow graph; returns the ComfyUI prompt_id."""
    client_id = client_id or str(uuid.uuid4())
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{COMFY_URL}/prompt",
            json={"prompt": workflow, "client_id": client_id},
        )
        r.raise_for_status()
        return r.json()["prompt_id"]


async def poll_result(prompt_id: str, timeout=300):
    """Poll /history until the prompt has outputs or the timeout elapses.

    A history entry with status_str == "error" raises immediately (before the
    outputs check) so failed jobs fail fast instead of hanging for the full
    timeout. Returns {"status": "success", "outputs": {node_id: {...}}} on
    success; raises TimeoutError otherwise.
    """
    async with httpx.AsyncClient(timeout=timeout) as c:
        for _ in range(max(1, timeout // 2)):
            r = await c.get(f"{COMFY_URL}/history/{prompt_id}")
            if r.status_code == 200:
                entry = r.json().get(prompt_id, {})
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(f"ComfyUI execution failed: {prompt_id}")
                outputs = entry.get("outputs")
                if outputs:
                    return {"status": "success", "outputs": outputs}
            await asyncio.sleep(2)
    raise TimeoutError(prompt_id)


async def get_view(filename: str) -> bytes:
    """Download a generated artifact from the ComfyUI /view endpoint."""
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.get(f"{COMFY_URL}/view", params={"filename": filename})
        r.raise_for_status()
        return r.content


def load_workflow(filename: str = None) -> dict:
    """Load a workflow JSON template from the workflows/ directory."""
    path = os.path.join(_WORKFLOWS_DIR, filename or DEFAULT_WORKFLOW_FILE)
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def render_workflow(template: dict, prompt: str) -> dict:
    """Return a deep copy of the template with __PROMPT__ substituted.

    The caller's template dict is never mutated.
    """
    workflow = copy.deepcopy(template)
    for node in workflow.values():
        inputs = node.get("inputs") if isinstance(node, dict) else None
        if isinstance(inputs, dict) and inputs.get("prompt") == PROMPT_PLACEHOLDER:
            inputs["prompt"] = prompt
    return workflow


def extract_output_filename(polled: dict):
    """Pull the first media filename out of a poll_result payload."""
    for node_outputs in (polled or {}).get("outputs", {}).values():
        if not isinstance(node_outputs, dict):
            continue
        for media_key in ("videos", "images", "gifs"):
            entries = node_outputs.get(media_key)
            if entries:
                name = entries[0].get("filename")
                if name:
                    return name
    return None
