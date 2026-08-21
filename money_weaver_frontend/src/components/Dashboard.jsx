import { useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Skeleton } from '@/components/ui/skeleton'
import { Play, Plus, Clock, Video, Zap, Settings, User, Eye, Mic, LogOut } from 'lucide-react'
// eslint-disable-next-line no-unused-vars
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import api from '@/services/api'
import { useAuthStore } from '@/store/authStore'
import { useProjects } from '@/hooks/useProjects'
import { useTasks } from '@/hooks/useTasks'
import { usePresets } from '@/hooks/usePresets'
import '../App.css'

const POLL_INTERVAL_MS = 5000

const ACTIVE_STATUSES = ['running', 'processing']

const isActive = (t) => ACTIVE_STATUSES.includes(t.status)

const getStatusColor = (status) => {
  switch (status) {
    case 'completed': return 'bg-green-500'
    case 'processing':
    case 'running': return 'bg-blue-500'
    case 'failed': return 'bg-red-500'
    default: return 'bg-gray-500'
  }
}

const getWorkflowIcon = (type) => {
  return type === 'generative' ? <Zap className="h-4 w-4" /> : <Video className="h-4 w-4" />
}

const ErrorRetryCard = ({ title, message, onRetry }) => (
  <div className="p-8 bg-slate-800/50 rounded-lg border border-slate-700 text-center">
    <div className="text-red-400 text-2xl mb-4">⚠️</div>
    <h3 className="text-lg font-bold text-white mb-2">{title}</h3>
    <p className="text-slate-400 mb-6">{message}</p>
    <Button onClick={onRetry} className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600">
      Retry
    </Button>
  </div>
)

const ProjectListSkeleton = () => (
  <div className="grid gap-4">
    {[0, 1].map((i) => (
      <Card key={i} className="bg-slate-800/50 border-slate-700">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Skeleton className="h-8 w-8 rounded-md bg-slate-700" />
              <div className="space-y-2">
                <Skeleton className="h-4 w-48 bg-slate-700" />
                <Skeleton className="h-3 w-64 bg-slate-700" />
              </div>
            </div>
            <Skeleton className="h-6 w-16 rounded-full bg-slate-700" />
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <Skeleton className="h-4 w-32 bg-slate-700" />
            <Skeleton className="h-8 w-28 bg-slate-700" />
          </div>
        </CardContent>
      </Card>
    ))}
  </div>
)

const TaskListSkeleton = () => (
  <div className="grid gap-4">
    {[0, 1].map((i) => (
      <Card key={i} className="bg-slate-800/50 border-slate-700">
        <CardHeader>
          <Skeleton className="h-4 w-40 bg-slate-700" />
          <Skeleton className="h-3 w-24 bg-slate-700" />
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Skeleton className="h-3 w-20 bg-slate-700" />
              <Skeleton className="h-3 w-10 bg-slate-700" />
            </div>
            <Skeleton className="h-2 w-full bg-slate-700" />
          </div>
        </CardContent>
      </Card>
    ))}
  </div>
)

const Dashboard = ({ onCreateVideo }) => {
  const navigate = useNavigate()

  const projectsQuery = useProjects()
  const tasksQuery = useTasks({
    // Keep the legacy live-status behaviour: while any task is in flight,
    // refetch the task list (which carries status + progress) every few seconds.
    refetchInterval: (query) => {
      const list = query.state.data ?? []
      return list.some(isActive) ? POLL_INTERVAL_MS : false
    },
  })
  const presetsQuery = usePresets()

  const projects = projectsQuery.data ?? []
  const tasks = tasksQuery.data ?? []
  const presets = presetsQuery.data ?? []

  const projectsLoading = projectsQuery.isLoading
  const tasksLoading = tasksQuery.isLoading
  const presetsLoading = presetsQuery.isLoading

  const [seedInput, setSeedInput] = useState('')
  const [isGeneratingSurprise, setIsGeneratingSurprise] = useState(false)
  const [surpriseTaskId, setSurpriseTaskId] = useState(null)

  const completedCount = projects.filter((p) => p.status === 'completed').length
  const successRate = projects.length ? Math.round((completedCount / projects.length) * 100) : 0

  useEffect(() => {
    if (projectsQuery.isError) {
      toast.error('Failed to load projects', {
        id: 'dashboard-projects-error',
        description: projectsQuery.error?.message,
      })
    }
  }, [projectsQuery.isError, projectsQuery.error])

  useEffect(() => {
    if (tasksQuery.isError) {
      toast.error('Failed to load tasks', {
        id: 'dashboard-tasks-error',
        description: tasksQuery.error?.message,
      })
    }
  }, [tasksQuery.isError, tasksQuery.error])

  useEffect(() => {
    if (presetsQuery.isError) {
      toast.error('Failed to load presets', {
        id: 'dashboard-presets-error',
        description: presetsQuery.error?.message,
      })
    }
  }, [presetsQuery.isError, presetsQuery.error])

  const handleLogout = async () => {
    try {
      await api.logout()
    } catch (err) {
      console.error('Logout error:', err)
    } finally {
      useAuthStore.getState().logout()
      navigate('/login')
    }
  }

  const handleSurpriseMe = async () => {
    setIsGeneratingSurprise(true)
    try {
      const result = await api.generateSurprise({ seed: seedInput || undefined })
      setSurpriseTaskId(result.task_id)
      // Poll task status
      const poll = setInterval(async () => {
        const task = await api.request(`/tasks/${surpriseTaskId}`)
        if (task.status !== 'running' && task.status !== 'processing') {
          clearInterval(poll)
          setIsGeneratingSurprise(false)
          toast.success('Surprise video generated!')
        }
      }, POLL_INTERVAL_MS)
    } catch (error) {
      console.error('Surprise me error:', error)
      toast.error('Failed to generate surprise')
      setIsGeneratingSurprise(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Header */}
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
                <p className="text-sm text-slate-400">AI Video Generation Platform</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <Button variant="outline" size="sm" onClick={() => navigate('/settings')}>
                <Settings className="h-4 w-4 mr-2" />
                Settings
              </Button>
              <Button variant="outline" size="sm" onClick={() => navigate('/profile')}>
                <User className="h-4 w-4 mr-2" />
                Profile
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="border-red-500/40 text-red-400 hover:bg-red-500/10 hover:text-red-300"
                onClick={handleLogout}
              >
                <LogOut className="h-4 w-4 mr-2" />
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Stats Cards */}
          <div className="lg:col-span-4 grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            {projectsLoading || tasksLoading ? (
              [0, 1, 2, 3].map((i) => (
                <Card key={i} className="bg-slate-800/50 border-slate-700">
                  <CardHeader className="pb-2">
                    <Skeleton className="h-4 w-24 bg-slate-700" />
                  </CardHeader>
                  <CardContent>
                    <Skeleton className="h-8 w-12 bg-slate-700" />
                  </CardContent>
                </Card>
              ))
            ) : (
              <>
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1 }}
                >
                  <Card className="bg-slate-800/50 border-slate-700">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-medium text-slate-400">Total Projects</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-white">{projects.length}</div>
                    </CardContent>
                  </Card>
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                >
                  <Card className="bg-slate-800/50 border-slate-700">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-medium text-slate-400">Active Tasks</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-white">
                        {tasks.filter(isActive).length}
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 }}
                >
                  <Card className="bg-slate-800/50 border-slate-700">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-medium text-slate-400">Completed</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-white">{completedCount}</div>
                    </CardContent>
                  </Card>
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.4 }}
                >
                  <Card className="bg-slate-800/50 border-slate-700">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-medium text-slate-400">Success Rate</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-white">{successRate}%</div>
                    </CardContent>
                  </Card>
                </motion.div>
              </>
            )}
          </div>

          {/* Main Content Area */}
          <div className="lg:col-span-3">
            <Tabs defaultValue="projects" className="space-y-6">
              <TabsList className="bg-slate-800/50 border-slate-700">
                <TabsTrigger value="projects">Projects</TabsTrigger>
                <TabsTrigger value="tasks">Active Tasks</TabsTrigger>
              </TabsList>

              <TabsContent value="projects" className="space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-semibold text-white">Your Projects</h2>
                  <Button className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600" onClick={onCreateVideo}>
                    <Plus className="h-4 w-4 mr-2" />
                    New Project
                  </Button>
                </div>

                {projectsQuery.isError ? (
                  <ErrorRetryCard
                    title="Failed to load projects"
                    message={projectsQuery.error?.message}
                    onRetry={() => projectsQuery.refetch()}
                  />
                ) : projectsLoading ? (
                  <ProjectListSkeleton />
                ) : projects.length > 0 ? (
                  <div className="grid gap-4">
                    {projects.map((project, index) => (
                      <motion.div
                        key={project.id}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.1 }}
                      >
                        <Card className="bg-slate-800/50 border-slate-700 hover:bg-slate-800/70 transition-colors">
                          <CardHeader>
                            <div className="flex items-center justify-between">
                              <div className="flex items-center space-x-3">
                                {getWorkflowIcon(project.workflow_type)}
                                <div>
                                  <CardTitle className="text-white">{project.title}</CardTitle>
                                  <CardDescription className="text-slate-400">
                                    {project.description}
                                  </CardDescription>
                                </div>
                              </div>
                              <Badge className={`${getStatusColor(project.status)} text-white`}>
                                {project.status}
                              </Badge>
                            </div>
                          </CardHeader>
                          <CardContent>
                            <div className="flex items-center justify-between">
                              <div className="flex items-center space-x-4 text-sm text-slate-400">
                                <span className="flex items-center">
                                  <Clock className="h-4 w-4 mr-1" />
                                  {new Date(project.created_at).toLocaleDateString()}
                                </span>
                                <Badge variant="outline" className="border-slate-600 text-slate-300">
                                  {project.workflow_type}
                                </Badge>
                              </div>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => navigate(`/projects/${project.id}`)}
                              >
                                <Eye className="h-4 w-4 mr-2" />
                                View Details
                              </Button>
                            </div>
                          </CardContent>
                        </Card>
                      </motion.div>
                    ))}
                  </div>
                ) : (
                  <div className="p-8 bg-slate-800/50 rounded-lg border border-slate-700 text-center">
                    <p className="text-slate-400">No projects yet. Create your first video project.</p>
                  </div>
                )}
              </TabsContent>

              <TabsContent value="tasks" className="space-y-4">
                <h2 className="text-xl font-semibold text-white">Active Tasks</h2>
                {tasksQuery.isError ? (
                  <ErrorRetryCard
                    title="Failed to load tasks"
                    message={tasksQuery.error?.message}
                    onRetry={() => tasksQuery.refetch()}
                  />
                ) : tasksLoading ? (
                  <TaskListSkeleton />
                ) : tasks.filter(isActive).length > 0 ? (
                  <div className="grid gap-4">
                    {tasks.filter(isActive).map((task, index) => (
                      <motion.div
                        key={task.id}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.1 }}
                      >
                        <Card className="bg-slate-800/50 border-slate-700">
                          <CardHeader>
                            <CardTitle className="text-white">
                              {task.task_type ? task.task_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Unknown Task'}
                            </CardTitle>
                            <CardDescription className="text-slate-400">
                              Project ID: {task.project_id}
                            </CardDescription>
                          </CardHeader>
                          <CardContent>
                            <div className="space-y-2">
                              <div className="flex items-center justify-between text-sm">
                                <span className="text-slate-400">Progress</span>
                                <span className="text-white">
                                  {task.progress !== undefined ? `${task.progress}%` : 'Unknown'}
                                </span>
                              </div>
                              <Progress value={task.progress || 0} className="h-2" />
                            </div>
                          </CardContent>
                        </Card>
                      </motion.div>
                    ))}
                  </div>
                ) : (
                  <div className="p-8 bg-slate-800/50 rounded-lg border border-slate-700 text-center">
                    <p className="text-slate-400">No active tasks right now.</p>
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </div>

          {/* Sidebar */}
          <div className="lg:col-span-1 space-y-6">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white">Quick Actions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Button className="w-full bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600" onClick={onCreateVideo}>
                  <Video className="h-4 w-4 mr-2" />
                  Assembler Video
                </Button>
                <Button className="w-full bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600" onClick={onCreateVideo}>
                  <Zap className="h-4 w-4 mr-2" />
                  Generative Video
                </Button>
                <Button variant="outline" className="w-full border-slate-600 text-slate-300 hover:bg-slate-700" onClick={() => navigate('/voice-cloning')}>
                  <Mic className="h-4 w-4 mr-2" />
                  Voice Cloning
                </Button>
                <Button variant="outline" className="w-full border-slate-600 text-slate-300 hover:bg-slate-700">
                  Batch Mix
                </Button>
              </CardContent>
            </Card>

            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white">Format Presets</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {presetsQuery.isError ? (
                  <p className="text-sm text-slate-500">Failed to load presets.</p>
                ) : presetsLoading ? (
                  <div className="space-y-2">
                    <Skeleton className="h-4 w-full bg-slate-700" />
                    <Skeleton className="h-4 w-3/4 bg-slate-700" />
                    <Skeleton className="h-4 w-1/2 bg-slate-700" />
                  </div>
                ) : presets.length > 0 ? (
                  presets.map((preset) => (
                    <div key={preset.id} className="flex items-center justify-between text-sm">
                      <span className="text-slate-300">{preset.name}</span>
                      <span className="text-xs text-slate-500">
                        {preset.width}×{preset.height}
                      </span>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">No presets available.</p>
                )}
              </CardContent>
            </Card>

            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white">System Status</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-400">API Server</span>
                  <Badge className="bg-green-500 text-white">Online</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-400">Celery Workers</span>
                  <Badge className="bg-green-500 text-white">3 Active</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-400">ComfyUI</span>
                  <Badge className="bg-green-500 text-white">Ready</Badge>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white">Surprise Me</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-slate-400">
                  Generate a random video idea and script.
                </p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    ref={seedRef}
                    value={seedInput}
                    onChange={(e) => setSeedInput(e.target.value)}
                    placeholder="Optional seed..."
                    className="bg-slate-700 border-slate-600 text-white rounded px-3 py-2 flex-1"
                  />
                  <Button
                    variant="primary"
                    onClick={handleSurpriseMe}
                    disabled={isGeneratingSurprise}
                  >
                    {isGeneratingSurprise ? (
                      <Skeleton className="h-4 w-4" />
                    ) : (
                      <Zap className="h-4 w-4 mr-2" />
                    )}
                    Surprise Me
                  </Button>
                </div>
                {surpriseTaskId && (
                  <div className="mt-3 text-xs text-slate-400">
                    Task ID: {surpriseTaskId}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  )
}

export default Dashboard