from flask import Blueprint, jsonify, request, g
from src.models.api_key import ApiKey
from src.services.llm_service import llm_service
from src.database import db
from src.auth import auth_required
import litellm
import os
import requests

# Configure LiteLLM to use the proxy for testing
litellm_proxy_url = os.getenv('LITELLM_PROXY_URL', 'http://localhost:8000')
litellm.api_base = f"{litellm_proxy_url}/v1"
litellm.master_key = os.getenv('LITELLM_MASTER_KEY', '')

api_keys_bp = Blueprint('api_keys', __name__)

@api_keys_bp.route('/api-keys', methods=['POST'])
@auth_required
def add_api_key():
    """Add a new API key"""
    data = request.json
    
    # Validate required fields
    if not data.get('name') or not data.get('provider') or not data.get('key'):
        return jsonify({'error': 'name, provider, and key are required'}), 400
    
    try:
        # Add API key using the service
        api_key = llm_service.add_api_key(
            user_id=g.current_user['id'],
            name=data['name'],
            provider=data['provider'],
            key=data['key']
        )
        
        return jsonify({
            'message': 'API key added successfully',
            'api_key': api_key.to_dict()
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_keys_bp.route('/api-keys/user/<int:user_id>', methods=['GET'])
@auth_required
def get_user_api_keys(user_id):
    """Get all API keys for a user"""
    if user_id != g.current_user['id']:
        return jsonify({'error': 'Forbidden'}), 403
    try:
        api_keys = llm_service.get_user_api_keys(g.current_user['id'])
        return jsonify({
            'api_keys': [key.to_dict() for key in api_keys]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_keys_bp.route('/api-keys/<int:api_key_id>', methods=['DELETE'])
@auth_required
def delete_api_key(api_key_id):
    """Delete an API key"""
    try:
        success = llm_service.delete_api_key(api_key_id, g.current_user['id'])
        if success:
            return jsonify({'message': 'API key deleted successfully'}), 200
        else:
            return jsonify({'error': 'API key not found or unauthorized'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_keys_bp.route('/api-keys/test', methods=['POST'])
@auth_required
def test_api_key():
    """Test an API key through the LiteLLM proxy"""
    data = request.json
    
    # Validate required fields
    if not data.get('provider') or not data.get('key'):
        return jsonify({'error': 'provider and key are required'}), 400
    
    try:
        # For testing through the proxy, we'll add the key to the proxy's configuration
        # For now, we'll do a direct test using the provided key
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
            # Updated to a currently supported model
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
            # Azure requires additional configuration which would be stored with the key
            test_model = "azure/gpt-4"
        elif data['provider'] == 'vertex':
            litellm.vertex_key = data['key']
            # Vertex requires additional configuration which would be stored with the key
            test_model = "vertex_ai/gemini-pro"
        elif data['provider'] == 'huggingface':
            litellm.huggingface_key = data['key']
            test_model = "huggingface/meta-llama/Llama-2-7b"
        elif data['provider'] == 'bedrock':
            litellm.bedrock_key = data['key']
            # Bedrock requires additional configuration which would be stored with the key
            test_model = "bedrock/anthropic.claude-v2"
        else:
            return jsonify({'error': 'Unsupported provider'}), 400
        
        # Test with a simple completion
        response = litellm.completion(
            model=test_model,
            messages=[{"role": "user", "content": "Hello, this is a test."}],
            max_tokens=10
        )
        
        return jsonify({
            'success': True,
            'message': 'API key is valid',
            'response': response.choices[0].message.content
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@api_keys_bp.route('/models', methods=['GET'])
@auth_required
def get_available_models():
    """Get available models from the LiteLLM proxy"""
    try:
        # Fetch models from the LiteLLM proxy
        headers = {
            "Authorization": f"Bearer {litellm.master_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{litellm_proxy_url}/v1/models",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            models_data = response.json()
            # Extract model names from the response
            model_names = []
            if 'data' in models_data:
                for model in models_data['data']:
                    if 'id' in model:
                        model_names.append(model['id'])
            
            return jsonify({
                'models': sorted(model_names)
            }), 200
        else:
            # Fallback to predefined models if proxy is not available
            predefined_models = [
                "gpt-4", "gpt-3.5-turbo",
                "claude-2", "claude-instant-1",
                "gemini-pro",
                "groq/llama-3.1-8b-instant",
                "groq/llama-3.1-70b-versatile",
                "groq/llama-3.1-405b-reasoning",
                "groq/mixtral-8x7b-32768",
                "groq/gemma-7b-it",
                "together_ai/mistralai/Mistral-7B-v0.1"
            ]
            return jsonify({
                'models': predefined_models
            }), 200
            
    except Exception as e:
        # Fallback to predefined models if there's an error
        predefined_models = [
            "gpt-4", "gpt-3.5-turbo",
            "claude-2", "claude-instant-1",
            "gemini-pro",
            "groq/llama-3.1-8b-instant",
            "groq/llama-3.1-70b-versatile",
            "groq/llama-3.1-405b-reasoning",
            "groq/mixtral-8x7b-32768",
            "groq/gemma-7b-it",
            "together_ai/mistralai/Mistral-7B-v0.1"
        ]
        return jsonify({
            'models': predefined_models,
            'error': str(e)
        }), 200  # Still return 200 but with error info

@api_keys_bp.route('/models/default', methods=['GET'])
@auth_required
def get_default_model():
    """Get the default model for script generation"""
    # Return a reasonable default model
    return jsonify({
        'default_model': 'groq/llama-3.1-70b-versatile'
    }), 200