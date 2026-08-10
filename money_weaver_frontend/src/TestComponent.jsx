import { useState, useEffect } from 'react'
import api from '@/services/api'

const TestComponent = () => {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const projects = await api.getProjects()
        const tasks = await api.getTasks()
        setData({ projects, tasks })
      } catch (err) {
        setError(err.message)
        console.error('API Error:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  if (loading) return <div>Loading...</div>
  if (error) return <div>Error: {error}</div>
  if (!data) return <div>No data</div>

  return (
    <div>
      <h2>Projects</h2>
      <pre>{JSON.stringify(data.projects, null, 2)}</pre>
      <h2>Tasks</h2>
      <pre>{JSON.stringify(data.tasks, null, 2)}</pre>
    </div>
  )
}

export default TestComponent