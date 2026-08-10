// Test to check if API service is working
console.log('API service test started');

// Directly include the API service code here for testing
const API_BASE_URL = 'http://localhost:5004/api';

class ApiService {
  async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    if (config.body && typeof config.body === 'object') {
      config.body = JSON.stringify(config.body);
    }

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      }
      
      return await response.text();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  async getProjects(userId = null) {
    const query = userId ? `?user_id=${userId}` : '';
    return this.request(`/projects${query}`);
  }

  async getTasks(projectId = null) {
    const query = projectId ? `?project_id=${projectId}` : '';
    return this.request(`/tasks${query}`);
  }
}

const api = new ApiService();

// Test the API service
api.getProjects()
  .then(projects => {
    console.log('Projects fetched successfully:', projects);
  })
  .catch(error => {
    console.error('Failed to fetch projects:', error);
  });

api.getTasks()
  .then(tasks => {
    console.log('Tasks fetched successfully:', tasks);
  })
  .catch(error => {
    console.error('Failed to fetch tasks:', error);
  });