// Test to check if API service is working
console.log('API service test started');

// Test direct fetch
fetch('http://localhost:5004/api/projects')
  .then(response => {
    console.log('Response status:', response.status);
    console.log('Response headers:', [...response.headers.entries()]);
    return response.json();
  })
  .then(data => {
    console.log('Projects data:', data);
  })
  .catch(error => {
    console.error('Fetch error:', error);
  });

// Test tasks endpoint
fetch('http://localhost:5004/api/tasks')
  .then(response => {
    console.log('Tasks response status:', response.status);
    return response.json();
  })
  .then(data => {
    console.log('Tasks data:', data);
  })
  .catch(error => {
    console.error('Tasks fetch error:', error);
  });