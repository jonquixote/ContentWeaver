// Simple test to verify API service
const testApiService = async () => {
  try {
    // Test fetch directly
    console.log('Testing direct fetch...');
    const response = await fetch('http://localhost:5004/api/projects');
    const data = await response.json();
    console.log('Direct fetch result:', data);
    
    // Test API service
    console.log('Testing API service...');
    const apiModule = await import('./services/api.js');
    const api = apiModule.default;
    const projects = await api.getProjects();
    console.log('API service result:', projects);
  } catch (error) {
    console.error('Test failed:', error);
  }
};

// Run the test
testApiService();