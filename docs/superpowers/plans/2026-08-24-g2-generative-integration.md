# G2: Generative End-to-End Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every generative affordance works end-to-end from every surface and lands results into adjacent manual inputs as editable text.

**Architecture:** One new backend route (`POST /api/enhance-prompt`) reusing `_chat_free_resilient` + `enhance` assignment; one new route (`POST /api/scripts/draft`) wrapping `generate_script` with the `script` assignment; a reusable `<EnhanceButton>` frontend control wired beside prompt/script inputs; wizard voice-step fal selection threaded through the assembler payload as `voice_override`; video target already labeled (G1).

**Tech Stack:** Existing FastAPI patterns, llm_service, react-query/msw frontend stack.

**Repo facts:** Root `/Volumes/JOHNNY DISK/MoneyWeaver`. Python `money_weaver_backend/venv/bin/python -m pytest` (baseline **403**). Frontend `cd money_weaver_frontend && npx vitest run` (baseline **39**) / `npx vite build`. Key integration points: `llm_service._chat_free_resilient`, `resolve_model_for`, `ScriptEditor` (`VideoCreationWizard.jsx:440`, value=`formData.scriptHtml`, onChange `(html,text)` syncing prompt at :210-212), assembler voice branch (`video_tasks.py:371-379`), `AssembleRequest` in `fastapi_app/routers/generation.py`.

---

### Task 1: POST /api/enhance-prompt + /api/scripts/draft routes

**Files:**
- Create: `money_weaver_backend/fastapi_app/routers/enhance.py`
- Modify: `money_weaver_backend/fastapi_app/main.py` (include router)
- Test: `money_weaver_backend/tests/test_enhance_draft.py`

- [ ] **Step 1: Failing tests**

```python
def test_enhance_uses_assignment_and_returns_text(client, auth_headers, monkeypatch):
    from fastapi_app.routers import enhance as enh
    monkeypatch.setattr(enh.llm_service, 'resolve_model_for',
                        lambda uid, task: 'poolside/laguna-s-2.1:free')
    captured = {}
    def fake_chat(user_id, model, messages, **kw):
        captured.update(user_id=user_id, model=model)
        return "A better prompt about volcanoes"
    monkeypatch.setattr(enh.llm_service, '_chat_free_resilient', fake_chat)
    r = client.post('/api/enhance-prompt', headers=auth_headers,
                    json={'text': 'volcano video'})
    assert r.status_code == 200
    assert r.json()['enhanced'] == 'A better prompt about volcanoes'
    assert captured['model'] == 'poolside/laguna-s-2.1:free'


def test_enhance_requires_text(client, auth_headers):
    assert client.post('/api/enhance-prompt', headers=auth_headers,
                       json={'text': '  '}).status_code == 400


def test_draft_script_returns_screenplay(client, auth_headers, monkeypatch):
    from fastapi_app.routers import enhance as enh
    monkeypatch.setattr(enh.llm_service, 'resolve_model_for',
                        lambda uid, task: {'script': 'assigned/m'}.get(task))
    seen = {}
    monkeypatch.setattr(enh.llm_service, 'generate_script',
                        lambda prompt, uid, model=None, **kw:
                        seen.update(model=model, uid=uid) or "SCENE 1: X\nEND")
    r = client.post('/api/scripts/draft', headers=auth_headers,
                    json={'topic': 'volcanoes', 'duration': 30})
    assert r.status_code == 200
    assert 'SCENE 1' in r.json()['script']
    assert seen['model'] == 'assigned/m'


def test_draft_rejects_blank_topic(client, auth_headers):
    assert client.post('/api/scripts/draft', headers=auth_headers,
                       json={'topic': ''}).status_code == 400
```

- [ ] **Step 2: RED**
- [ ] **Step 3: Implement** `enhance.py`:

```python
from fastapi import APIRouter, Depends, HTTPException

from fastapi_app.deps import current_user
from src.services.llm_service import llm_service, resolve_model_for

router = APIRouter(prefix='/api', tags=['enhance'])


@router.post('/enhance-prompt')
def enhance_prompt(body: dict, user=Depends(current_user)):
    text = (body.get('text') or '').strip()
    if not text:
        raise HTTPException(400, 'text is required')
    style_hint = body.get('style_hint') or 'vivid, concrete, cinematic detail'
    model = resolve_model_for(user.id, 'enhance')
    try:
        enhanced = llm_service._chat_free_resilient(
            user.id, model,
            [{"role": "system", "content": "You rewrite short video-generation prompts. Return ONLY the improved prompt, no commentary."},
             {"role": "user", "content": f"Improve this prompt (add {style_hint}). Keep it under 120 words:\n\n{text}"}],
            temperature=0.8, max_tokens=300)
        return {"enhanced": (enhanced or '').strip() or text}
    except Exception as e:
        raise HTTPException(503, f"Prompt enhancement unavailable: {e}")


@router.post('/scripts/draft')
def draft_script(body: dict, user=Depends(current_user)):
    topic = (body.get('topic') or '').strip()
    if not topic:
        raise HTTPException(400, 'topic is required')
    duration = int(body.get('duration') or 30)
    model = body.get('model') or resolve_model_for(user.id, 'script')
    niche_id = body.get('niche_id') or None
    try:
        script = llm_service.generate_script(topic, user.id, model=model,
                                             duration=duration, niche_id=niche_id)
        return {"script": script}
    except Exception as e:
        raise HTTPException(503, f"Script drafting unavailable: {e}")
```

main.py: `from fastapi_app.routers import enhance` + `app.include_router(enhance.router)` following sibling lines.

- [ ] **Step 4: GREEN + full suite**
- [ ] **Step 5: Commit** `feat: enhance-prompt + scripts/draft routes (assignment-aware)`

---

### Task 2: <EnhanceButton> component

**Files:**
- Create: `money_weaver_frontend/src/components/EnhanceButton.jsx`
- Modify: `money_weaver_frontend/src/services/api.js` (+enhancePrompt(text))
- Modify: `money_weaver_frontend/src/test/handlers.js` (default handler)
- Test: `money_weaver_frontend/src/__tests__/enhanceButton.test.jsx`

- [ ] **Step 1: Failing tests** (copy imports/setup from modelAssignments.test.jsx):

```jsx
test('calls onEnhanced with response text', async () => {
  server.use(http.post('*/api/enhance-prompt', () =>
    HttpResponse.json({ enhanced: 'better words here' })))
  const onEnhanced = vi.fn()
  render(<EnhanceButton text="draft" onEnhanced={onEnhanced} />)
  fireEvent.click(screen.getByRole('button', { name: /enhance/i }))
  await waitFor(() => expect(onEnhanced).toHaveBeenCalledWith('better words here'))
})

test('shows error toast and does not call onEnhanced on failure', async () => {
  server.use(http.post('*/api/enhance-prompt', () =>
    HttpResponse.json({ error: 'unavailable' }, { status: 503 })))
  const onEnhanced = vi.fn()
  render(<EnhanceButton text="draft" onEnhanced={onEnhanced} />)
  fireEvent.click(screen.getByRole('button', { name: /enhance/i }))
  await waitFor(() => expect(screen.getByRole('button')).toBeEnabled())
  expect(onEnhanced).not.toHaveBeenCalled()
})
```

- [ ] **Step 2: RED**
- [ ] **Step 3: Implement**: small outline Button with Wand2 icon (lucide), disabled while pending or empty text; onClick → `api.enhancePrompt(text)` → `onEnhanced(enhanced)` + success toast; error toast on failure (sonner, match existing). api.js method mirrors randomIdea.
- [ ] **Step 4: GREEN + build**
- [ ] **Step 5: Commit** `feat: EnhanceButton with undo-safe callback contract`

---

### Task 3: Wire EnhanceButton + Draft Script into wizard

**Files:**
- Modify: `money_weaver_frontend/src/components/VideoCreationWizard.jsx`
- Test: extend `money_weaver_frontend/src/__tests__/wizardOverrides.test.jsx` (or new file, same conventions)

- [ ] **Step 1: Failing tests**

```jsx
test('enhance wand replaces prompt text', async () => {
  // msw: enhance -> {enhanced: 'IMPROVED PROMPT'}
  // render wizard (step 1), type 'rough idea' into prompt textarea
  // click Enhance button (aria-label "Enhance prompt")
  // await textarea value === 'IMPROVED PROMPT'
})

test('draft script fills editor via script assignment', async () => {
  // msw: scripts/draft -> {script: '**Scene 1: Intro**\nVoiceover: "hello"'}
  // render wizard step 1, ensure title+prompt filled (so Draft enabled)
  // click 'Draft Script'
  // await screen.findByText(/Scene 1/i) inside editor region
})
```

Assert against real DOM the way existing wizard tests do (findByLabelText etc.). For editor
content assertion use the container's textContent via the wrapper ref pattern existing tests use
for ScriptEditor, or assert `handleScriptChange` effect indirectly by checking the storyboard
step canProceed gate flips (simpler: query editor paragraph text).

- [ ] **Step 2: RED**
- [ ] **Step 3: Implement**
  - Import EnhanceButton + ApiService. Beside the prompt Label row (step 1 ~line 418): `<EnhanceButton text={formData.prompt} onEnhanced={(t) => handleInputChange('prompt', t)} />`.
  - Next to Randomize card button: second button "Draft Script" (Sparkles icon), disabled without topic; onClick → `ApiService.draftScript({topic: formData.prompt || formData.title, duration, niche_id: formData.niche_id || undefined})`; on result: build editor HTML — escape HTML then wrap bold scene headers:
    ```js
    const esc = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;')
    const html = esc(script).split(/\n/).map(line =>
      /^\*\*.*\*\*$/.test(line.trim())
        ? `<p><strong>${line.trim().slice(2,-2)}</strong></p>`
        : `<p>${line.trim()}</p>`).join('')
    ```
    then `handleScriptChange('<div>'+html+'</div>', script)`; if editor had content show `toast.confirm`-style overwrite guard using existing confirm pattern (grep window.confirm usage; follow it).
  - api.js: `draftScript(payload)` POST `/scripts/draft`.
- [ ] **Step 4: GREEN + build**
- [ ] **Step 5: Commit** `feat: wizard enhance wand + draft script into editor`

---

### Task 4: voice_override threading through assembler

**Files:**
- Modify: `money_weaver_backend/fastapi_app/routers/generation.py` (AssemblerRequest + dispatch kwargs)
- Modify: `money_weaver_backend/src/tasks/video_tasks.py` (accept voice_override; fal branch prefers it over assignment)
- Test: extend `money_weaver_backend/tests/test_assignment_consumption.py`

- [ ] **Step 1: Failing test**

```python
def test_assembler_voice_override_beats_assignment(monkeypatch, client, auth_headers):
    """Explicit fal voice id from wizard beats stored voice_tts assignment."""
    from src.tasks import video_tasks as vt
    resolved = {}
    monkeypatch.setattr(vt, 'resolve_model_for',
                        lambda uid, task: resolved.setdefault(task, 'auto'))
    # drive assembler happy path (test_tasks.py harness verbatim) posting
    # voice_override='fal-ai/kokoro-tts'; assert vt.fal_adapter.render called once
    # with endpoint 'fal-ai/kokoro-tts'
```

Also assert default path unchanged: existing assembler tests must stay green untouched.

- [ ] **Step 2: RED**
- [ ] **Step 3: Implement**
  - `AssemblerRequest`: `voice_override: Optional[str] = None`; dispatch passes `voice_override=data.get('voice_override')` into `.delay(...)`; task signature adds `voice_override=None`.
  - Voice branch precedence in assembler TTS section: explicit owned voice (existing) → `voice_override` if startswith('fal-ai/') → assignment `fal-ai/*` → local chain.
- [ ] **Step 4: GREEN + full suite**
- [ ] **Step 5: Commit** `feat: assembler voice_override threads wizard fal voice selection`

---

### Task 5: G2 close-out

- [ ] Full backend ≥405 green; coverage ≥55; frontend vitest ≥41 green; build ok.
- [ ] Live smoke: boot both servers; probe user: enhance-prompt 200 with fake-keyed 503 fallback message shape; draft blank-topic 400.
- [ ] Update `.superpowers/sdd/progress.md`; push contentweaver main.
