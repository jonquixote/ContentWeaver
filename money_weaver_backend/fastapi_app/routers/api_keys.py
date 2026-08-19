import os
from typing import Optional

import litellm
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from sqlalchemy.orm import Session

from fastapi_app.db import get_db
from fastapi_app.deps import current_user
from src.models.api_key import ApiKey
from src.models.model_preference import ModelPreference
from src.services.key_encryption import encrypt_key
from src.services.providers.registry import registry
from src.validation import require_fields

# Configure LiteLLM to use the proxy for testing
litellm_proxy_url = os.getenv('LITELLM_PROXY_URL', 'http://localhost:8000')
litellm.api_base = f"{litellm_proxy_url}/v1"
litellm.master_key = os.getenv('LITELLM_MASTER_KEY', '')

router = APIRouter(prefix='/api/api-keys', tags=['api-keys'])
models_router = APIRouter(prefix='/api', tags=['models'])


class ApiKeyCreate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    key: Optional[str] = None


class ApiKeyTest(BaseModel):
    provider: Optional[str] = None
    key: Optional[str] = None


@router.post('', status_code=201)
def add_api_key(body: ApiKeyCreate, user=Depends(current_user), session=Depends(get_db)):
    """Add a new API key"""
    data = body.model_dump()

    try:
        require_fields(data, ['name', 'provider', 'key'])
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        api_key = ApiKey(
            user_id=user.id,
            name=data['name'],
            provider=data['provider'],
            key=encrypt_key(data['key'])
        )
        session.add(api_key)
        session.commit()
        return {
            'message': 'API key added successfully',
            'api_key': api_key.to_dict()
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get('/user/{user_id}')
def get_user_api_keys(user_id: int, user=Depends(current_user), session=Depends(get_db)):
    """Get all API keys for a user"""
    if user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    try:
        api_keys = session.query(ApiKey).filter_by(user_id=user.id).all()
        return {
            'api_keys': [key.to_dict() for key in api_keys]
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete('/{api_key_id}')
def delete_api_key(api_key_id: int, user=Depends(current_user), session=Depends(get_db)):
    """Delete an API key"""
    try:
        api_key = session.query(ApiKey).filter_by(id=api_key_id, user_id=user.id).first()
        if api_key:
            session.delete(api_key)
            session.commit()
            return {'message': 'API key deleted successfully'}
        raise HTTPException(404, 'API key not found or unauthorized')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post('/test')
def test_api_key(body: ApiKeyTest, user=Depends(current_user)):
    """Test an API key through the LiteLLM proxy"""
    data = body.model_dump()

    try:
        require_fields(data, ['provider', 'key'])
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        if data['provider'] == 'openai':
            litellm.openai_key = data['key']
            test_model = "gpt-4"
        elif data['provider'] == 'anthropic':
            litellm.anthropic_key = data['key']
            test_model = "claude-2"
        elif data['provider'] == 'google':
            litellm.google_key = data['key']
            test_model = "gemini-pro"
        elif data['provider'] == 'groq':
            litellm.groq_key = data['key']
            test_model = "groq/llama-3.1-8b-instant"
        elif data['provider'] == 'openrouter':
            litellm.openrouter_key = data['key']
            test_model = "openrouter/google/gemini-pro"
        elif data['provider'] == 'replicate':
            litellm.replicate_key = data['key']
            test_model = "replicate/meta/llama-3-8b"
        elif data['provider'] == 'togetherai':
            litellm.togetherai_key = data['key']
            test_model = "together_ai/mistralai/Mistral-7B-v0.1"
        elif data['provider'] == 'azure':
            litellm.azure_key = data['key']
            test_model = "azure/gpt-4"
        elif data['provider'] == 'vertex':
            litellm.vertex_key = data['key']
            test_model = "vertex_ai/gemini-pro"
        elif data['provider'] == 'huggingface':
            litellm.huggingface_key = data['key']
            test_model = "huggingface/meta-llama/Llama-2-7b"
        elif data['provider'] == 'bedrock':
            litellm.bedrock_key = data['key']
            test_model = "bedrock/anthropic.claude-v2"
        else:
            raise HTTPException(400, 'Unsupported provider')

        response = litellm.completion(
            model=test_model,
            messages=[{"role": "user", "content": "Hello, this is a test."}],
            max_tokens=10
        )

        return {
            'success': True,
            'message': 'API key is valid',
            'response': response.choices[0].message.content
        }

    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=400, content={
            'success': False,
            'error': str(e)
        })


@models_router.get('/models')
def get_available_models(user=Depends(current_user)):
    """Get available models from the registry (live, cache-backed)"""
    return {"models": registry.list_models()}


@models_router.get('/models/default')
def get_default_model(user=Depends(current_user), db: Session = Depends(get_db)):
    """Get the default model for script generation (per-user prefs -> best free)"""
    prefs = db.query(ModelPreference).filter_by(user_id=user.id).first()
    prefs_dict = prefs.to_dict() if prefs else None
    model = registry.resolve(prefs_dict, "script")
    return {"default_model": model}