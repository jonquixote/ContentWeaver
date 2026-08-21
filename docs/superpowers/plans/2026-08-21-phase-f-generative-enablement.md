# Phase F: Generative Enablement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the placeholder Wan2.2 workflow template with a real graph ported from kijai/ComfyUI-WanVideoWrapper, make the `model` param select fp8 vs default template, and cover the enabled Celery path with a mocked end-to-end test.

**Architecture:** The workflow JSON stays a repo asset (`workflows/wan22_t2v_api.json`) in ComfyUI **API format** (`{"prompt": {"<node_id>": {"class_type": ..., "inputs": ...}}}`). `comfy_client.render_workflow` already deep-copies and substitutes placeholders — extend it to substitute prompt/width/height/seed by node-id map declared at the top of the module, so template internals can change without code changes. `video_tasks.generate_generative_video_task` picks `wan22_fp8_api.json` when `"fp8"` appears in the model string.

**Tech Stack:** ComfyUI HTTP API (existing gateway), kijai/ComfyUI-WanVideoWrapper example workflows (Apache-2.0), pytest mocks.

**Repo facts:** `/Volumes/JOHNNY DISK/MoneyWeaver`; `money_weaver_backend/venv/bin/python -m pytest`; baseline 360+ tests. Existing pieces: `src/services/comfy_client.py` (`health`, `queue_workflow`, `poll_result`, `get_view`, `render_workflow`), `workflows/wan22_t2v_api.json` (placeholder with `__PROMPT__`), flag gate in `video_tasks.py` (~466-471: `COMFY_ENABLED=='true'` + `health()`), router passes `model` (~generation.py:226). Tests mock httpx at class level; follow `tests/test_comfy_client.py` conventions.

---

### Task 1: Port real Wan2.2 t2v graph into API-format template

**Files:**
- Modify: `money_weaver_backend/workflows/wan22_t2v_api.json`
- Create: `money_weaver_backend/workflows/wan22_fp8_api.json`
- Test: `money_weaver_backend/tests/test_comfy_client.py`

- [ ] **Step 1: Fetch the upstream example**

Run:

```bash
curl -sL https://raw.githubusercontent.com/kijai/ComfyUI-WanVideoWrapper/main/example_workflows/wanvideo_T2V_example.json -o /tmp/wan_t2v_example.json
python3 -c "import json; d=json.load(open('/tmp/wan_t2v_example.json')); print(list(d.keys())[:5]); print(len(d.get('nodes', d.get('prompt', {}))))"
```

If the file is UI-format (has `"nodes"`, `"links"` keys), convert to API format: for each node in
`nodes`, emit `{"class_type": node["type"], "inputs": {input_name: value_or_link}}` where links
(`[node_id, slot]`) become `["<node_id>", <slot>]`. Write the conversion helper as a one-off
script in the report (not committed) or do it by hand if the graph is small. The committed
artifact MUST be API format: `{"prompt": {...}}` or bare `{node_id: {...}}` matching whatever
`comfy_client.queue_workflow` sends today (check its POST body construction and match it).

- [ ] **Step 2: Parameterize the template**

In the converted JSON, set these input values to placeholder tokens (keep everything else
exactly as upstream):

- The positive text-encode node's `text` → `"__PROMPT__"`
- The empty/latent video node's `width` → `__WIDTH__`, `height` → `__HEIGHT__`
- The sampler/seed node's `seed` → `__SEED__`
- Model loader nodes keep upstream defaults (model paths are server-side concerns)

Record the substituted node ids in a comment-free sidecar:
`workflows/wan22_t2v_api.meta.json`:

```json
{
  "source": "kijai/ComfyUI-WanVideoWrapper example_workflows/wanvideo_T2V_example.json (Apache-2.0)",
  "params": {"prompt": "<positive_text_node_id>", "width": "<latent_node_id>", "height": "<latent_node_id>", "seed": "<sampler_node_id>"}
}
```

- [ ] **Step 3: Create the fp8 variant**

Copy the file to `workflows/wan22_fp8_api.json`; change only model-name inputs to their fp8
equivalents (e.g. `Wan2_2-T2V-A14B-fp8.safetensors` style names per upstream README); same
placeholders, same meta structure with `"variant": "fp8"` added.

- [ ] **Step 4: Commit templates**

```bash
git add money_weaver_backend/workflows/
git commit -m "feat: real Wan2.2 t2v API templates (default + fp8) from WanWrapper examples"
```

---

### Task 2: render_workflow parameter substitution + meta-driven ids

**Files:**
- Modify: `money_weaver_backend/src/services/comfy_client.py` (`render_workflow`)
- Modify: `money_weaver_backend/workflows/wan22_t2v_api.json` (ensure tokens)
- Test: `money_weaver_backend/tests/test_comfy_client.py`

- [ ] **Step 1: Write failing tests**

Append to `money_weaver_backend/tests/test_comfy_client.py`:

```python
def test_render_workflow_substitutes_all_params():
    from src.services import comfy_client as cc

    template = {
        "1": {"class_type": "WanVideoTextEncode", "inputs": {"text": "__PROMPT__"}},
        "2": {"class_type": "EmptyHunyuanLatentVideo", "inputs": {"width": "__WIDTH__", "height": "__HEIGHT__"}},
        "3": {"class_type": "KSampler", "inputs": {"seed": "__SEED__"}},
    }
    meta = {"params": {"prompt": "1", "width": "2", "height": "2", "seed": "3"}}

    wf = cc.render_workflow(template, prompt="a cat", width=480, height=832, seed=42, meta=meta)
    assert wf["1"]["inputs"]["text"] == "a cat"
    assert wf["2"]["inputs"]["width"] == 480
    assert wf["2"]["inputs"]["height"] == 832
    assert wf["3"]["inputs"]["seed"] == 42


def test_render_workflow_token_scan_without_meta():
    from src.services import comfy_client as cc

    template = {"1": {"class_type": "X", "inputs": {"text": "__PROMPT__"}}}
    wf = cc.render_workflow(template, prompt="p", width=None, height=None, seed=None)
    assert wf["1"]["inputs"]["text"] == "p"


def test_render_workflow_does_not_mutate_template():
    from src.services import comfy_client as cc
    template = {"1": {"class_type": "X", "inputs": {"text": "__PROMPT__"}}}
    snapshot = json.dumps(template)
    cc.render_workflow(template, prompt="p", width=1, height=1, seed=1)
    assert json.dumps(template) == snapshot
```

(Add `import json` at top of the test file if absent.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests/test_comfy_client.py -v --no-cov`
Expected: FAIL — `_load_template_meta` missing / signature mismatch with current render_workflow.

- [ ] **Step 3: Implement**

In `comfy_client.py` (adapt to the existing `render_workflow` signature — read it first; keep
backward compat by giving new kwargs None defaults):

```python
_WORKFLOWS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "workflows",
)

_TOKENS = {"prompt": "__PROMPT__", "width": "__WIDTH__",
           "height": "__HEIGHT__", "seed": "__SEED__"}


def _load_template_meta(template_name):
    base = template_name.replace(".json", "")
    try:
        with open(os.path.join(_WORKFLOWS_DIR, f"{base}.meta.json")) as fh:
            return json.load(fh)
    except (FileNotFoundError, ValueError):
        return {}


def render_workflow(template, prompt=None, width=None, height=None, seed=None, meta=None):
    """Deep-copy template and substitute __PROMPT__/__WIDTH__/__HEIGHT__/__SEED__
    tokens. Node ids come from `meta['params']`; falls back to scanning for the
    token anywhere in the graph."""
    import copy
    wf = copy.deepcopy(template)
    params = {"prompt": prompt, "width": width, "height": height, "seed": seed}
    meta_params = (meta or {}).get("params") or {}
    for key, value in params.items():
        if value is None:
            continue
        token = _TOKENS[key]
        node_ids = []
        if meta_params.get(key):
            node_ids.append(str(meta_params[key]))
        else:
            node_ids = [
                nid for nid, node in wf.items()
                if any(v == token for v in (node.get("inputs") or {}).values())
            ]
        for nid in node_ids:
            if nid in wf and token in wf[nid].get("inputs", {}):
                wf[nid]["inputs"][token] = value
    return wf
```

The caller (video_tasks generative branch, Task 3) loads meta itself and passes it in:

```python
from src.services.comfy_client import load_template_meta
meta = load_template_meta(template_name)
workflow = render_workflow(_load_comfy_template(template_name), prompt=prompt,
                           width=width, height=height, seed=seed, meta=meta)
```

Expose `load_template_meta = _load_template_meta` (public alias) in comfy_client so callers
avoid a private import. Keep the private name for any existing internal references.

- [ ] **Step 4: Run tests + commit**

Focused then full suite green.

```bash
git add money_weaver_backend/src/services/comfy_client.py money_weaver_backend/tests/test_comfy_client.py
git commit -m "feat: meta-driven workflow parameter substitution in comfy_client"
```

---

### Task 3: model param selects fp8 template

**Files:**
- Modify: `money_weaver_backend/src/tasks/video_tasks.py` (enabled branch ~475-500)
- Test: `money_weaver_backend/tests/test_comfy_client.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_comfy_client.py`:

```python
def test_generative_task_selects_fp8_template_for_fp8_model(monkeypatch):
    """model containing 'fp8' must load wan22_fp8_api.json."""
    import json
    from src.tasks import video_tasks as vt

    loaded = {}
    def fake_json_load(path):
        loaded["path"] = path
        return {"1": {"class_type": "Fake", "inputs": {"text": "__PROMPT__"}}}

    monkeypatch.setattr(vt, "_load_comfy_template", fake_json_load)
    monkeypatch.setattr(vt.comfy_client, "health", lambda: True)
    monkeypatch.setattr(vt.comfy_client, "queue_workflow",
                        lambda wf, cid=None: "pid")
    monkeypatch.setattr(vt.comfy_client, "poll_result",
                        lambda pid, timeout=300: {"status": "success", "outputs": {"9": {"gifs": [{"filename": "out.mp4"}]}}})
    monkeypatch.setattr(vt.comfy_client, "get_view", lambda fn: b"MP4fake")

    vt._run_generative_pipeline(project_id=1, prompt="cat", model="wan22-fp8",
                                work_dir="/tmp")
    assert loaded["path"].endswith("wan22_fp8_api.json")
```

Note: `_run_generative_pipeline` does not exist yet — extract it in Step 3. If extraction is
too invasive, instead patch at the current call site and assert on a new
`_template_name_for_model(model)` helper:

```python
def test_template_name_for_model():
    from src.tasks.video_tasks import _template_name_for_model
    assert _template_name_for_model("wan22-fp8") == "wan22_fp8_api.json"
    assert _template_name_for_model(None) == "wan22_t2v_api.json"
    assert _template_name_for_model("wan22") == "wan22_t2v_api.json"
```

Prefer this smaller version unless the task body is trivially extractable.

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — helper undefined.

- [ ] **Step 3: Implement**

In `video_tasks.py` near the generative task:

```python
def _template_name_for_model(model):
    if model and "fp8" in str(model).lower():
        return "wan22_fp8_api.json"
    return "wan22_t2v_api.json"


def _load_comfy_template(name):
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "workflows", name,
    )
    with open(path) as fh:
        return json.load(fh)
```

(Verify `import json` exists in the module; check the real relative depth from
`src/tasks/video_tasks.py` to `workflows/` — it is 3 dirname levels: tasks → src → backend.
Match how other modules locate repo assets, e.g. niche_profile's `_NICHE_DIR`.)

In the enabled branch, replace the hardcoded template load with:

```python
workflow = _load_comfy_template(_template_name_for_model(model))
```

and thread `model` through `render_workflow(...)` substitutions (Task 2 signature).

- [ ] **Step 4: Run tests + full suite + commit**

```bash
git add money_weaver_backend/src/tasks/video_tasks.py money_weaver_backend/tests/test_comfy_client.py
git commit -m "feat: model param selects fp8/default Wan2.2 template in generative task"
```

---

### Task 4: Enabled-path end-to-end Celery test (mocked)

**Files:**
- Test: `money_weaver_backend/tests/test_comfy_client.py`

- [ ] **Step 1: Write the test**

Append (reuse the fixture/mocking idioms of `test_generative_happy_path` in
`tests/test_fastapi_generation.py` for DB/task-record setup — read that test first):

```python
def test_enabled_generative_task_full_path(monkeypatch, db_session):
    """COMFY_ENABLED=true + healthy Comfy: task queues, polls, downloads,
    stores output, marks record completed. All network faked."""
    import os
    from src.tasks import video_tasks as vt

    monkeypatch.setenv("COMFY_ENABLED", "true")
    monkeypatch.setattr(vt.comfy_client, "health", lambda: True)
    monkeypatch.setattr(vt.comfy_client, "queue_workflow", lambda wf, cid=None: "prompt-1")

    poll_calls = {"n": 0}
    def fake_poll(pid, timeout=300):
        poll_calls["n"] += 1
        if poll_calls["n"] < 2:
            return {"status": "running", "outputs": {}}
        return {"status": "success",
                "outputs": {"9": {"gifs": [{"filename": "wan_00001.mp4"}]}}}
    monkeypatch.setattr(vt.comfy_client, "poll_result", fake_poll)
    monkeypatch.setattr(vt.comfy_client, "get_view", lambda fn: b"MP4DATA")

    stored = {}
    monkeypatch.setattr(vt.storage, "put_object",
                        lambda key, data: stored.setdefault(key, data))

    # create project + task record rows using the same helpers the fastapi
    # generation tests use; then invoke the celery task synchronously:
    #   vt.generate_generative_video_task.run(project_id=pid, prompt="cat",
    #                                         voice_id=None, model=None)
    # Assert: stored key matches clips/generative namespace convention used in
    # the task body; task record status == 'completed'; no exception raised.
```

Fill the DB-setup section by copying the closest existing happy-path test verbatim (grep
`generate_generative_video_task` in tests/) — change only assertions. If the task writes the
downloaded bytes to a temp file before put_object, also assert that cleanup happened
(`finally` unlink), mirroring T5 review expectations.

- [ ] **Step 2: Run to verify it fails or exposes bugs**

Expected: either PASS immediately (wiring already correct) or FAIL revealing a concrete bug —
fix the bug, not the test, unless the test misread the contract.

- [ ] **Step 3: Full suite + commit**

```bash
git add money_weaver_backend/tests/test_comfy_client.py
git commit -m "test: enabled-path e2e coverage for generative ComfyUI task"
```

---

### Task 5: Phase F close-out

- [ ] **Step 1:** Full suite green; coverage ≥55.
- [ ] **Step 2:** Validate both template JSONs parse and contain all four tokens:
  `python3 -c "import json;t=json.load(open('money_weaver_backend/workflows/wan22_t2v_api.json'));s=str(t);assert all(t_ in s for t_ in ['__PROMPT__','__WIDTH__','__HEIGHT__','__SEED__'])"` (same for fp8).
- [ ] **Step 3:** Update `.superpowers/sdd/progress.md`.
