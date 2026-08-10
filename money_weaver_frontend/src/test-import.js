// Test to verify API service is working
console.log('Starting API service test...');

// Test direct fetch
fetch('http://localhost:5004/api/projects')
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  })
  .then(data => {
    console.log('Direct fetch successful:', data);
  })
  .catch(error => {
    console.error('Direct fetch failed:', error);
  });

// Test API service
import('./services/api.js')
  .then(apiModule => {
    const api = apiModule.default;
    return api.getProjects();
  })
  .then(projects => {
    console.log('API service test successful:', projects);
  })
  .catch(error => {
    console.error('API service test failed:', error);
  });