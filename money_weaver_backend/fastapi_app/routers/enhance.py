from fastapi import APIRouter, Depends, HTTPException

from fastapi_app.deps import current_user
from src.services.llm_service import llm_service, resolve_model_for

llm_service.resolve_model_for = resolve_model_for

router = APIRouter(prefix='/api', tags=['enhance'])


@router.post('/enhance-prompt')
def enhance_prompt(body: dict, user=Depends(current_user)):
    text = (body.get('text') or '').strip()
    if not text:
        raise HTTPException(400, 'text is required')
    style_hint = body.get('style_hint') or 'vivid, concrete, cinematic detail'
    model = llm_service.resolve_model_for(user.id, 'enhance')
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
    model = body.get('model') or llm_service.resolve_model_for(user.id, 'script')
    niche_id = body.get('niche_id') or None
    try:
        script = llm_service.generate_script(topic, user.id, model=model,
                                             duration=duration, niche_id=niche_id)
        return {"script": script}
    except Exception as e:
        raise HTTPException(503, f"Script drafting unavailable: {e}")


@router.post('/generate/description')
def generate_description(body: dict, user=Depends(current_user)):
    premise = (body.get('premise') or '').strip()
    if not premise:
        raise HTTPException(400, 'premise is required')
    script = (body.get('script') or '').strip()[:2000]
    model = llm_service.resolve_model_for(user.id, 'script')
    try:
        description = llm_service._chat_free_resilient(
            user.id, model,
            [{"role": "system", "content":
              "You write one-paragraph platform video descriptions (<=80 words), "
              "no hashtags unless asked. Return ONLY the description text."},
             {"role": "user", "content":
              f"Premise: {premise}\n\nScript excerpt:\n{script or '(none yet)'}"}],
            temperature=0.7, max_tokens=200)
        return {"description": (description or '').strip()}
    except Exception as e:
        raise HTTPException(503, f"Description generation unavailable: {e}")
