import { useAuthStore } from '@/store/authStore'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5004/api'

class ApiService {
  constructor() {
    this.token = useAuthStore.getState().token || null
  }

  setToken(token) {
    this.token = token
    useAuthStore.getState().setToken(token)
  }

  async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`
    const token = useAuthStore.getState().token
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
        ...options.headers,
      },
      ...options,
    }

    if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
      config.body = JSON.stringify(config.body)
    }

    if (config.body instanceof FormData) {
      delete config.headers['Content-Type']
    }

    try {
      const response = await fetch(url, config)
      
      if (!response.ok) {
        if (response.status === 401) {
          // Unauthorized - token might be expired
          this.setToken(null)
          window.location.href = '/login'
        }
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`)
      }
      
      const contentType = response.headers.get('content-type')
      if (contentType && contentType.includes('application/json')) {
        return await response.json()
      }
      
      return await response.text()
    } catch (error) {
      console.error('API request failed:', error)
      throw error
    }
  }

  // Auth endpoints
  async login(credentials) {
    return this.request('/auth/login', {
      method: 'POST',
      body: credentials,
      headers: {
        'Content-Type': 'application/json'
      }
    })
  }

  async register(userData) {
    return this.request('/auth/register', {
      method: 'POST',
      body: userData,
      headers: {
        'Content-Type': 'application/json'
      }
    })
  }

  async logout() {
    try {
      await this.request('/auth/logout', {
        method: 'POST',
      })
    } catch (error) {
      console.error('Logout error:', error)
    } finally {
      this.setToken(null)
    }
  }

  // User endpoints
  async getUsers() {
    return this.request('/users')
  }

  async createUser(userData) {
    return this.request('/users', {
      method: 'POST',
      body: userData,
    })
  }

  // Project endpoints
  async getProjects(userId = null) {
    const query = userId ? `?user_id=${userId}` : ''
    return this.request(`/projects${query}`)
  }

  async createProject(projectData) {
    return this.request('/projects', {
      method: 'POST',
      body: projectData,
    })
  }

  async getProject(projectId) {
    return this.request(`/projects/${projectId}`)
  }

  async updateProject(projectId, projectData) {
    return this.request(`/projects/${projectId}`, {
      method: 'PUT',
      body: projectData,
    })
  }

  async deleteProject(projectId) {
    return this.request(`/projects/${projectId}`, {
      method: 'DELETE',
    })
  }

  // Task endpoints
  async getTasks(projectId = null) {
    const query = projectId ? `?project_id=${projectId}` : ''
    return this.request(`/tasks${query}`)
  }

  async getTask(taskId) {
    return this.request(`/tasks/${taskId}`)
  }

  async getTaskStatus(taskId) {
    return this.request(`/tasks/${taskId}/status`)
  }

  // Video generation endpoints
  async generateAssemblerVideo(projectId, prompt, options = {}) {
    return this.request('/generate/assembler', {
      method: 'POST',
      body: { 
        project_id: projectId, 
        prompt,
        ...options
      },
    })
  }

  async generateGenerativeVideo(projectId, prompt, options = {}) {
    return this.request('/generate/generative', {
      method: 'POST',
      body: {
        project_id: projectId,
        prompt,
        ...options,
      },
    })
  }

  async batchMixVideos(projectId, variations) {
    return this.request('/batch-mix', {
      method: 'POST',
      body: { project_id: projectId, variations },
    })
  }

  async getCeleryTaskStatus(taskId) {
    return this.request(`/task-status/${taskId}`)
  }

  // Voice endpoints
  async getVoices() {
    return this.request('/voices')
  }

  async presignUpload(ext) {
    return this.request(`/uploads/presign?ext=${encodeURIComponent(ext)}`)
  }

  // PUT audio bytes to a presigned upload URL. The backend PUT-proxy (local
  // storage mode) needs the Bearer token; S3/R2 presigned URLs reject extra
  // Authorization headers, so only attach it when the target is our own API.
  async putUpload(uploadUrl, file, contentType) {
    const headers = { 'Content-Type': contentType }
    try {
      const target = new URL(uploadUrl)
      const base = new URL(API_BASE_URL)
      if (target.host === base.host) {
        headers['Authorization'] = `Bearer ${this.token}`
      }
    } catch {
      /* not a parseable URL — leave headers as-is */
    }
    const response = await fetch(uploadUrl, {
      method: 'PUT',
      headers,
      body: file,
    })
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.error || `Upload failed! status: ${response.status}`)
    }
    // S3/R2 presigned PUTs answer 200 with an empty body; the local PUT-proxy
    // returns JSON. Never let a body-parse failure abort a successful upload.
    return response.json().catch(() => ({}))
  }

  async createVoice(payload) {
    return this.request('/voices', {
      method: 'POST',
      body: payload,
    })
  }

  async previewVoice(voiceId, text) {
    return this.request(`/voices/${voiceId}/preview`, {
      method: 'POST',
      body: { text },
    })
  }

  async deleteVoice(voiceId) {
    return this.request(`/voices/${voiceId}`, {
      method: 'DELETE',
    })
  }

  // Authed URL for server-asset routes (/final/...) that can't send a Bearer
  // header (e.g. <audio src>). The backend accepts the token via ?token=.
  getAuthedAssetUrl(path) {
    const base = API_BASE_URL.replace(/\/api\/?$/, '')
    const sep = path.includes('?') ? '&' : '?'
    return `${base}${path}${this.token ? `${sep}token=${encodeURIComponent(this.token)}` : ''}`
  }

  // API Key endpoints
  async getApiKeys(userId) {
    return this.request(`/api-keys/user/${userId}`)
  }

  async addApiKey(apiKeyData) {
    return this.request('/api-keys', {
      method: 'POST',
      body: apiKeyData,
    })
  }

  async deleteApiKey(apiKeyId, userId) {
    return this.request(`/api-keys/${apiKeyId}`, {
      method: 'DELETE',
      body: { user_id: userId },
    })
  }

  async testApiKey(provider, key) {
    return this.request('/api-keys/test', {
      method: 'POST',
      body: { provider, key },
    })
  }

  // Model endpoints
  async getAvailableModels() {
    return this.request('/models')
  }

  async getDefaultModel() {
    return this.request('/models/default')
  }
}

export default new ApiService()

