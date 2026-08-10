// Simple test to check if modules are working
console.log('Module test started');

// Test if we can import the API service
try {
  import('./services/api.js')
    .then(apiModule => {
      console.log('API module imported successfully');
      const api = apiModule.default;
      console.log('API service available:', typeof api);
      
      // Test a simple method
      if (api && typeof api.getProjects === 'function') {
        console.log('getProjects method exists');
      } else {
        console.log('getProjects method missing');
      }
    })
    .catch(error => {
      console.error('Failed to import API module:', error);
    });
} catch (error) {
  console.error('Import test failed:', error);
}