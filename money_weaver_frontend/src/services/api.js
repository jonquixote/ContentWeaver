const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5004/api'

class ApiService {
  constructor() {
    this.token = localStorage.getItem('authToken')
  }

  setToken(token) {
    this.token = token
    if (token) {
      localStorage.setItem('authToken', token)
    } else {
      localStorage.removeItem('authToken')
    }
  }

  async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...(this.token && { 'Authorization': `Bearer ${this.token}` }),
        ...options.headers,
      },
      ...options,
    }

    if (config.body && typeof config.body === 'object') {
      config.body = JSON.stringify(config.body)
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

  async generateGenerativeVideo(projectId, prompt) {
    return this.request('/generate/generative', {
      method: 'POST',
      body: { project_id: projectId, prompt },
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
  async getAvailableVoices() {
    return this.request('/voices')
  }

  async cloneVoice(audioFile, text) {
    const formData = new FormData()
    formData.append('audio', audioFile)
    formData.append('text', text)
    
    return this.request('/clone-voice', {
      method: 'POST',
      body: formData,
      headers: {
        // Remove Content-Type to let browser set it with boundary for multipart/form-data
      }
    })
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

