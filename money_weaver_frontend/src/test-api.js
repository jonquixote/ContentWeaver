import api from '@/services/api'

// Test the API service
const testApi = async () => {
  try {
    console.log('Testing API service...')
    const projects = await api.getProjects()
    console.log('Projects:', projects)
    
    const tasks = await api.getTasks()
    console.log('Tasks:', tasks)
  } catch (error) {
    console.error('API test failed:', error)
  }
}

testApi()