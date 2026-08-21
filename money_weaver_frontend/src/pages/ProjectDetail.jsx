import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { ScrollArea } from '@/components/ui/scroll-area'
import { ArrowLeft, Clock, Play, RefreshCw, Video, Scissors, Youtube } from 'lucide-react'
import VideoPlayer from '@/components/VideoPlayer'
// eslint-disable-next-line no-unused-vars
import { motion } from 'framer-motion'
import { toast } from 'sonner'
import api, { resolveMediaUrl } from '@/services/api'
import '../App.css'

const getStatusColor = (status) => {
  switch (status) {
    case 'completed': return 'bg-green-500'
    case 'processing':
    case 'running': return 'bg-blue-500'
    case 'failed': return 'bg-red-500'
    case 'draft': return 'bg-gray-500'
    default: return 'bg-gray-500'
  }
}

const parseTaskResult = (task) => {
  if (!task?.result) return {}
  try {
    const parsed = typeof task.result === 'string' ? JSON.parse(task.result) : task.result
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch (err) {
    console.error('Failed to parse task result:', err)
    return {}
  }
}

// Give up polling after this many consecutive status-check failures so a
// persistently erroring endpoint can't keep the upload button stuck forever.
const YOUTUBE_MAX_POLL_FAILURES = 10

// clips/detect expects a storage key; the project stores a backend-relative
// URL (/final/..., videos/...) — strip scheme/path prefix and query.
const toVideoKey = (url) => {
  if (!url) return null
  return url.split('?')[0].replace(/^\//, '') || null
}

const ProjectDetail = () => {
  const { id } = useParams()
  const navigate = useNavigate()
  const [project, setProject] = useState(null)
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [isDetectingClips, setIsDetectingClips] = useState(false)
  const [isUploadingYoutube, setIsUploadingYoutube] = useState(false)
  const [youtubeTaskId, setYoutubeTaskId] = useState(null)
  const youtubePollRef = useRef(null)
  const youtubeFailuresRef = useRef(0)
  const [youtubeStatus, setYoutubeStatus] = useState(null)
  const [youtubeUrl, setYoutubeUrl] = useState(null)

  useEffect(() => () => {
    if (youtubePollRef.current) clearInterval(youtubePollRef.current)
  }, [])

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const [projectData, tasksData] = await Promise.all([
          api.getProject(id),
          api.getTasks(id)
        ])
        setProject(projectData)
        setTasks(tasksData)
        setError(null)
      } catch (err) {
        console.error('Failed to fetch project:', err)
        setError('Failed to load project. Please try again later.')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [id])

  // Poll task status for live progress
  const activeTask = tasks.find(t => t.status !== 'completed' && t.status !== 'failed')
  useEffect(() => {
    if (!activeTask) return

    const interval = setInterval(async () => {
      try {
        const status = await api.getTaskStatus(activeTask.id)
        setTasks(prev => prev.map(t => {
          if (t.id !== activeTask.id) return t
          const updated = { ...t, status: status.status, progress: status.progress }
          if (status.message) updated.error_message = status.message
          if (status.video_url) {
            updated.result = JSON.stringify({ ...parseTaskResult(t), video_url: status.video_url })
          }
          return updated
        }))
        if (status.status === 'completed' || status.status === 'failed') {
          clearInterval(interval)
        }
      } catch (err) {
        console.error('Failed to fetch task status:', err)
      }
    }, 5000)

    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTask?.id])

  const handleGenerateClips = async () => {
    if (!videoKey) {
      toast.error('No rendered video available for clip detection yet.')
      return
    }
    setIsDetectingClips(true)
    try {
      const result = await api.detectClips(project.id, videoKey)
      setTasks(prev => [{ id: result.task_id, task_type: 'viral_clip_detection', status: 'pending', progress: 0 }, ...prev])
      toast.success('Viral clip detection started')
    } catch (err) {
      console.error('Failed to start clip detection:', err)
      toast.error(err.message || 'Failed to start viral clip detection.')
    } finally {
      setIsDetectingClips(false)
    }
  }

  const stopYoutubePolling = () => {
    if (youtubePollRef.current) {
      clearInterval(youtubePollRef.current)
      youtubePollRef.current = null
    }
  }

  const pollYoutubeTask = async (taskId) => {
    try {
      const task = await api.getTask(taskId)
      setYoutubeStatus(task.status)
      youtubeFailuresRef.current = 0
      if (task.status === 'completed') {
        const result = parseTaskResult(task)
        if (result.youtube_url) setYoutubeUrl(result.youtube_url)
        toast.success('YouTube upload completed!')
        setIsUploadingYoutube(false)
        return true
      }
      if (task.status === 'failed') {
        toast.error(task.error_message || 'YouTube upload failed.')
        setIsUploadingYoutube(false)
        return true
      }
    } catch (err) {
      console.error('Failed to fetch YouTube task status:', err)
      youtubeFailuresRef.current += 1
      if (youtubeFailuresRef.current >= YOUTUBE_MAX_POLL_FAILURES) {
        toast.error('Lost track of the YouTube upload — stopped checking. Please retry.')
        setIsUploadingYoutube(false)
        return true
      }
    }
    return false
  }

  const handleYoutubeUpload = async () => {
    setIsUploadingYoutube(true)
    youtubeFailuresRef.current = 0
    try {
      const result = await api.uploadToYoutube(project.id, 'private')
      setYoutubeTaskId(result.task_id)
      setYoutubeStatus('pending')
      const interval = setInterval(async () => {
        const done = await pollYoutubeTask(result.task_id)
        if (done) {
          stopYoutubePolling()
        }
      }, 3000)
      youtubePollRef.current = interval
    } catch (err) {
      console.error('Failed to start YouTube upload:', err)
      toast.error(err.message || 'Failed to start YouTube upload.')
      setIsUploadingYoutube(false)
    }
  }

  const handleConnectYoutube = async () => {
    try {
      const data = await api.getYoutubeAuthUrl()
      if (!data?.url) throw new Error('No authorization URL returned')
      window.open(data.url, '_blank', 'noopener')
    } catch (err) {
      console.error('Failed to get YouTube auth URL:', err)
      toast.error(err.message || 'YouTube connect is not available right now.')
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500 mx-auto"></div>
          <p className="mt-4 text-slate-300">Loading project...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
        <div className="text-center p-8 bg-slate-800/50 rounded-lg border border-slate-700 max-w-md">
          <div className="text-red-400 text-2xl mb-4">⚠️</div>
          <h2 className="text-xl font-bold text-white mb-2">Error Loading Project</h2>
          <p className="text-slate-300 mb-6">{error}</p>
          <Button
            onClick={() => window.location.reload()}
            className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
          >
            Retry
          </Button>
        </div>
      </div>
    )
  }

  if (!project) return null

  const latestTask = tasks.length > 0 ? tasks[0] : null
  const taskResult = parseTaskResult(latestTask)
  const videoUrl = resolveMediaUrl(taskResult.video_url || project.video_url)
  const thumbnailUrl = resolveMediaUrl(taskResult.thumbnail_url)
  const progress = latestTask?.progress ?? 0
  const videoKey = toVideoKey(taskResult.video_url || project.video_url)

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 260, damping: 20 }}
                className="h-10 w-10 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 flex items-center justify-center"
              >
                <Play className="h-6 w-6 text-white" />
              </motion.div>
              <div>
                <h1 className="text-2xl font-bold text-white">MoneyWeaver</h1>
                <p className="text-sm text-slate-400">Project Details</p>
              </div>
            </div>
            <Button variant="outline" size="sm" onClick={() => navigate('/dashboard')}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Dashboard
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Project Info */}
          <div className="lg:col-span-2 space-y-6">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-white text-2xl">{project.title}</CardTitle>
                      <CardDescription className="text-slate-400 mt-1">
                        {project.description}
                      </CardDescription>
                    </div>
                    <Badge className={`${getStatusColor(project.status)} text-white`}>
                      {project.status}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <h3 className="text-sm font-medium text-slate-400">Workflow Type</h3>
                      <p className="text-white capitalize mt-1">{project.workflow_type}</p>
                    </div>
                    <div>
                      <h3 className="text-sm font-medium text-slate-400">Created</h3>
                      <p className="text-white flex items-center mt-1">
                        <Clock className="h-4 w-4 mr-1" />
                        {new Date(project.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                  <div>
                    <h3 className="text-sm font-medium text-slate-400">Script</h3>
                    <ScrollArea className="h-[200px] w-full rounded-md border border-slate-700 p-4 mt-2">
                      <pre className="text-slate-300 whitespace-pre-wrap font-sans">
                        {project.script || 'No script generated yet'}
                      </pre>
                    </ScrollArea>
                  </div>
                </CardContent>
              </Card>
            </motion.div>

            {/* Video Player */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <CardTitle className="text-white flex items-center">
                    <Video className="h-5 w-5 mr-2 text-purple-400" />
                    Generated Video
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {videoUrl ? (
                    <div className="space-y-4">
                      <div className="relative rounded-lg overflow-hidden bg-slate-900">
                        {thumbnailUrl && !videoUrl && (
                          <img
                            src={thumbnailUrl}
                            alt={`${project.title} thumbnail`}
                            className="w-full aspect-video object-cover"
                          />
                        )}
                        <VideoPlayer src={videoUrl} poster={thumbnailUrl || undefined} />
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
                          onClick={() => navigate('/create')}
                        >
                          <RefreshCw className="h-4 w-4 mr-2" />
                          Re-generate Video
                        </Button>
                        {taskResult.video_url && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="border-slate-600 text-slate-300 hover:bg-slate-600"
                            onClick={() => {
                              const link = document.createElement('a')
                              link.href = videoUrl
                              link.download = `video-${project.id}.mp4`
                              document.body.appendChild(link)
                              link.click()
                              document.body.removeChild(link)
                            }}
                          >
                            Download
                          </Button>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="text-center p-8 bg-slate-900 rounded-lg border border-slate-700">
                      <p className="text-slate-300 mb-4">No video available for this project yet.</p>
                      <Button
                        className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
                        onClick={() => navigate('/create')}
                      >
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Generate Video
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </div>

          {/* Sidebar: Task Progress */}
          <div className="lg:col-span-1 space-y-6">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <CardTitle className="text-white">Generation Progress</CardTitle>
                </CardHeader>
                <CardContent>
                  {latestTask ? (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-slate-400">{latestTask.task_type?.replace(/_/g, ' ')}</span>
                        <Badge className={`${getStatusColor(latestTask.status)} text-white`}>
                          {latestTask.status}
                        </Badge>
                      </div>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-slate-400">Progress</span>
                          <span className="text-white">{progress}%</span>
                        </div>
                        <Progress value={progress} className="h-2" />
                      </div>
                      {latestTask.error_message && (
                        <p className="text-sm text-red-400">{latestTask.error_message}</p>
                      )}
                      {latestTask.status === 'completed' && (
                        <p className="text-sm text-green-400">Video generation completed successfully!</p>
                      )}
                    </div>
                  ) : (
                    <div className="text-center py-6">
                      <p className="text-slate-300">No generation tasks yet.</p>
                      <Button
                        className="mt-4 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
                        onClick={() => navigate('/create')}
                      >
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Re-generate Video
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>

            {/* Distribution & Clips */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
            >
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <CardTitle className="text-white">Distribution & Clips</CardTitle>
                  <CardDescription className="text-slate-400">
                    Find viral moments or publish privately to YouTube.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Button
                    variant="outline"
                    className="w-full border-slate-600 text-slate-300 hover:bg-slate-700"
                    onClick={handleGenerateClips}
                    disabled={isDetectingClips || !videoKey}
                  >
                    <Scissors className="h-4 w-4 mr-2" />
                    {isDetectingClips ? 'Starting...' : 'Generate viral clips'}
                  </Button>
                  {!videoKey && (
                    <p className="text-xs text-slate-500">
                      Render a video first — clip detection needs a source video.
                    </p>
                    )}
                  <Button
                    variant="outline"
                    className="w-full border-red-500/40 text-red-400 hover:bg-red-500/10 hover:text-red-300"
                    onClick={handleYoutubeUpload}
                    disabled={isUploadingYoutube || Boolean(youtubeTaskId && youtubeStatus !== 'failed')}
                  >
                    <Youtube className="h-4 w-4 mr-2" />
                    {isUploadingYoutube ? 'Starting...' : 'Upload to YouTube (private)'}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full border-slate-600 text-slate-300 hover:bg-slate-700"
                    onClick={handleConnectYoutube}
                  >
                    <Youtube className="h-4 w-4 mr-2" />
                    Connect YouTube
                  </Button>
                  {youtubeTaskId && !youtubeUrl && (
                    <p className="text-xs text-slate-400">
                      Upload task #{youtubeTaskId} — {youtubeStatus || 'pending'}...
                    </p>
                  )}
                  {youtubeUrl && (
                    <a
                      href={youtubeUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm text-purple-300 hover:text-purple-200 underline break-all"
                    >
                      {youtubeUrl}
                    </a>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </div>
        </div>
      </main>
    </div>
  )
}

export default ProjectDetail
