// Test to check if API endpoints are accessible
console.log('API endpoint test started');

// Test projects endpoint
fetch('http://localhost:5004/api/projects')
  .then(response => {
    console.log('Projects endpoint status:', response.status);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  })
  .then(data => {
    console.log('Projects data length:', data.length);
    console.log('First project:', data[0]);
  })
  .catch(error => {
    console.error('Projects endpoint error:', error);
  });

// Test tasks endpoint
fetch('http://localhost:5004/api/tasks')
  .then(response => {
    console.log('Tasks endpoint status:', response.status);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  })
  .then(data => {
    console.log('Tasks data length:', data.length);
    console.log('First task:', data[0]);
  })
  .catch(error => {
    console.error('Tasks endpoint error:', error);
  });