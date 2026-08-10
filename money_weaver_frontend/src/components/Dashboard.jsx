import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Play, Plus, Clock, Video, Zap, Settings, User, Eye, Download, PlayCircle, Mic } from 'lucide-react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import api from '@/services/api'
import { 
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import '../App.css'

// Helper function to format markdown for audio transcripts
const formatScriptMarkdown = (script) => {
  if (!script) return "No script generated yet";

  // Split the script into lines for processing
  const lines = script.split('\n');
  let formattedLines = [];
  
  lines.forEach(line => {
    if (line.startsWith('## ') || line.startsWith('# ')) {
      // Format headers
      formattedLines.push(`<strong class="block text-lg my-3 script-content scene">${line.replace(/^#+\s*/, '')}</strong>`);
    } else if (/^\d+\.\s/.test(line)) {
      // Format numbered scenes
      formattedLines.push(`<div class="my-3 p-2 bg-slate-700 rounded"><strong class="script-content scene">${line}</strong></div>`);
    } else if (/^(\w+(?:\s+\w+)*):\s*(.*)/.test(line)) {
      // Format dialogue lines (Speaker: text)
      const match = line.match(/^(\w+(?:\s+\w+)*):\s*(.*)/);
      formattedLines.push(`<div class="my-2"><span class="font-semibold script-content speaker">${match[1]}:</span> <span class="script-content">${match[2]}</span></div>`);
    } else if (line.startsWith('[') && line.endsWith(']')) {
      // Format action descriptions in brackets
      formattedLines.push(`<em class="script-content action">${line}</em>`);
    } else if (line.trim() === '') {
      // Handle empty lines
      formattedLines.push('<br />');
    } else {
      // Regular text
      formattedLines.push(`<span class="script-content">${line}</span>`);
    }
  });
  
  return formattedLines.join('');
};

const Dashboard = ({ onCreateVideo }) => {
  const [projects, setProjects] = useState([])
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedProject, setSelectedProject] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [videoError, setVideoError] = useState(false)
  const navigate = useNavigate()

  // Fetch real data from the backend
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        console.log('Fetching data from API...')
        // For now, we'll use a default user ID of 1
        // In a real app, you'd get this from authentication
        const [projectsData, tasksData] = await Promise.all([
          api.getProjects(),
          api.getTasks()
        ])
        
        console.log('Projects data:', projectsData)
        console.log('Tasks data:', tasksData)
        
        setProjects(projectsData)
        setTasks(tasksData)
        setError(null)
      } catch (err) {
        console.error('Failed to fetch data:', err)
        setError('Failed to load data. Please try again later.')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  // Poll for task updates
  useEffect(() => {
    if (tasks.length === 0) return

    const interval = setInterval(async () => {
      try {
        const updatedTasks = await Promise.all(
          tasks.map(async (task) => {
            if (task.status !== 'completed' && task.celery_task_id) {
              try {
                const status = await api.getCeleryTaskStatus(task.celery_task_id)
                return {
                  ...task,
                  status: status.state.toLowerCase(),
                  progress: status.current || 0
                }
              } catch (err) {
                console.error('Failed to fetch task status:', err)
                return task
              }
            }
            return task
          })
        )
        setTasks(updatedTasks)
      } catch (err) {
        console.error('Failed to update task statuses:', err)
      }
    }, 5000) // Poll every 5 seconds

    return () => clearInterval(interval)
  }, [tasks])

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

  const getWorkflowIcon = (type) => {
    return type === 'generative' ? <Zap className="h-4 w-4" /> : <Video className="h-4 w-4" />
  }

  const handleViewDetails = (project) => {
    setSelectedProject(project)
    setIsModalOpen(true)
  }

  const closeDetailsModal = () => {
    setIsModalOpen(false)
    setSelectedProject(null)
    setVideoError(false)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500 mx-auto"></div>
          <p className="mt-4 text-slate-300">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
        <div className="text-center p-8 bg-slate-800/50 rounded-lg border border-slate-700 max-w-md">
          <div className="text-red-400 text-2xl mb-4">⚠️</div>
          <h2 className="text-xl font-bold text-white mb-2">Error Loading Data</h2>
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Project Details Modal */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] bg-slate-800 border-slate-700 overflow-hidden flex flex-col">
          {selectedProject && (
            <div>
              <DialogHeader className="flex-shrink-0">
                <DialogTitle className="text-white text-2xl">{selectedProject.title}</DialogTitle>
                <DialogDescription className="text-slate-400">
                  {selectedProject.description}
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4 overflow-hidden flex-grow">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <h3 className="text-sm font-medium text-slate-400">Status</h3>
                    <Badge className={`${getStatusColor(selectedProject.status)} text-white mt-1`}>
                      {selectedProject.status}
                    </Badge>
                  </div>
                  <div>
                    <h3 className="text-sm font-medium text-slate-400">Workflow Type</h3>
                    <div className="flex items-center mt-1">
                      {getWorkflowIcon(selectedProject.workflow_type)}
                      <span className="text-white ml-2 capitalize">{selectedProject.workflow_type}</span>
                    </div>
                  </div>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-slate-400">Created</h3>
                  <p className="text-white">
                    {new Date(selectedProject.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex-grow overflow-hidden">
                  <h3 className="text-sm font-medium text-slate-400">Script</h3>
                  <ScrollArea className="h-[200px] w-full rounded-md border border-slate-700 p-4 mt-1">
                    <div 
                      className="script-content"
                      dangerouslySetInnerHTML={{ 
                        __html: formatScriptMarkdown(selectedProject.script) || "No script generated yet" 
                      }}
                    />
                  </ScrollArea>
                </div>
                {selectedProject.video_url && (
                  <div>
                    <h3 className="text-sm font-medium text-slate-400">Video</h3>
                    <div className="mt-2">
                      <div className="relative pt-[56.25%] rounded-lg overflow-hidden bg-slate-900">
                                                {videoError ? (
                          <div className="absolute inset-0 flex flex-col items-center justify-center text-white p-4 text-center bg-slate-800">
                            <p className="mb-4">Unable to play video directly</p>
                            {videoError.isHTML ? (
                              <p className="text-sm text-amber-400 mb-4">
                                The video file does not appear to exist at the specified location.
                              </p>
                            ) : (
                              <p className="text-sm text-slate-400 mb-2">
                                URL Type: {selectedProject.video_url.startsWith('http') ? 'HTTP URL' : 
                                          selectedProject.video_url.startsWith('blob:') ? 'Blob URL' : 
                                          selectedProject.video_url.startsWith('data:') ? 'Data URL' : 
                                          selectedProject.video_url.startsWith('/') ? 'Relative Path' :
                                          'Other'}
                              </p>
                            )}
                            <p className="text-xs text-slate-500 mb-2">Relative URL: {selectedProject.video_url}</p>
                            <p className="text-xs text-slate-500 mb-4 break-all">Absolute URL: {selectedProject.video_url.startsWith('/') ? `http://localhost:5004${selectedProject.video_url}` : selectedProject.video_url}</p>
                            {videoError.isHTML ? (
                              <p className="text-xs text-amber-400 mb-4">
                                The server returned an HTML page instead of a video file. The video may still be processing or the file path may be incorrect.
                              </p>
                            ) : (
                              <p className="text-xs text-amber-400 mb-4">Check browser console for detailed error information</p>
                            )}
                            <div className="flex gap-2">
                              <Button 
                                variant="default" 
                                className="bg-purple-600 hover:bg-purple-700"
                                onClick={() => window.open(selectedProject.video_url.startsWith('/') ? `http://localhost:5004${selectedProject.video_url}` : selectedProject.video_url, '_blank')}
                              >
                                Open in New Tab
                              </Button>
                              <Button 
                                variant="outline"
                                className="border-slate-600 text-slate-300 hover:bg-slate-700"
                                onClick={() => {
                                  // Convert relative URL to absolute if needed
                                  const absoluteUrl = selectedProject.video_url.startsWith('/') ? `http://localhost:5004${selectedProject.video_url}` : selectedProject.video_url;
                                  
                                  // Check if it's a blob or data URL
                                  if (absoluteUrl.startsWith('blob:') || absoluteUrl.startsWith('data:')) {
                                    // For blob URLs, we need to fetch the data first
                                    fetch(absoluteUrl)
                                      .then(response => response.blob())
                                      .then(blob => {
                                        const url = window.URL.createObjectURL(blob);
                                        const link = document.createElement('a');
                                        link.href = url;
                                        link.download = `video-${selectedProject.id}.mp4`;
                                        document.body.appendChild(link);
                                        link.click();
                                        document.body.removeChild(link);
                                        window.URL.revokeObjectURL(url);
                                      })
                                      .catch(err => {
                                        console.error("Error downloading blob:", err);
                                        // Fallback to opening in new tab
                                        window.open(absoluteUrl, '_blank');
                                      });
                                  } else {
                                    // For regular URLs, try direct download first
                                    const link = document.createElement('a');
                                    link.href = absoluteUrl;
                                    link.download = `video-${selectedProject.id}.mp4`;
                                    // Try to download, if it fails open in new tab
                                    link.onerror = () => {
                                      window.open(absoluteUrl, '_blank');
                                    };
                                    document.body.appendChild(link);
                                    link.click();
                                    document.body.removeChild(link);
                                  }
                                }}
                              >
                                Download
                              </Button>
                            </div>
                          </div>
                        ) : (
                                                    <video 
                            src={selectedProject.video_url.startsWith('/') ? `http://localhost:5004${selectedProject.video_url}` : selectedProject.video_url}
                            controls 
                            className="absolute top-0 left-0 w-full h-full"
                            onError={(e) => {
                              console.error("Error loading video:", e);
                              console.log("Video URL:", selectedProject.video_url);
                              console.log("Absolute URL:", selectedProject.video_url.startsWith('/') ? `http://localhost:5004${selectedProject.video_url}` : selectedProject.video_url);
                              // Try to fetch the URL to see what content is actually returned
                              const absoluteUrl = selectedProject.video_url.startsWith('/') ? `http://localhost:5004${selectedProject.video_url}` : selectedProject.video_url;
                              fetch(absoluteUrl)
                                .then(response => {
                                  console.log("URL fetch response:", response.status);
                                  console.log("Content-Type:", response.headers.get('Content-Type'));
                                  console.log("Content-Length:", response.headers.get('Content-Length'));
                                  
                                  // Check if it's actually a video file
                                  const contentType = response.headers.get('Content-Type');
                                  const isVideo = contentType && contentType.startsWith('video/');
                                  const isHTML = contentType && contentType.startsWith('text/html');
                                  
                                  if (isHTML) {
                                    console.warn("Warning: Content-Type is HTML - file may not exist");
                                  } else if (!isVideo) {
                                    console.warn("Warning: Content-Type is not a video type:", contentType);
                                  }
                                  
                                  // Check content length
                                  const contentLength = response.headers.get('Content-Length');
                                  if (contentLength === '0' || contentLength === null) {
                                    console.warn("Warning: Content-Length is zero or null");
                                  }
                                  
                                  // Store response data for use in the next then block
                                  return response.text().then(content => ({
                                    content,
                                    status: response.status,
                                    contentType: contentType,
                                    isHTML: isHTML,
                                    isVideo: isVideo,
                                    contentLength: contentLength
                                  }));
                                })
                                .then(({content, status, contentType, isHTML, isVideo, contentLength}) => {
                                  console.log("First 500 characters of content:", content.substring(0, 500));
                                  // Check if it looks like HTML (might be a 404 page)
                                  const looksLikeHTML = content.trim().startsWith('<!DOCTYPE html') || content.trim().startsWith('<html');
                                  if (looksLikeHTML) {
                                    console.warn("Warning: Content appears to be HTML, not a video file");
                                  }
                                  
                                  // Set a more specific error state
                                  setVideoError({
                                    isHTML: looksLikeHTML || isHTML,
                                    contentType: looksLikeHTML ? 'html' : contentType,
                                    status: status
                                  });
                                })
                                .catch(err => {
                                  console.error("URL fetch error:", err);
                                  setVideoError(true);
                                });
                            }}
                          />
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2 mt-2">
                        <Button 
                          variant="outline" 
                          size="sm" 
                          className="border-slate-600 text-slate-300 hover:bg-slate-600"
                          onClick={() => {
                            navigator.copyText(selectedProject.video_url);
                            // Could add a toast notification here
                          }}
                        >
                          Copy URL
                        </Button>
                        <Button 
                          variant="outline" 
                          size="sm" 
                          className="border-slate-600 text-slate-300 hover:bg-slate-600"
                          onClick={() => {
                            const link = document.createElement('a');
                            link.href = selectedProject.video_url;
                            link.download = `video-${selectedProject.id}.mp4`;
                            document.body.appendChild(link);
                            link.click();
                            document.body.removeChild(link);
                          }}
                        >
                          <Download className="h-4 w-4 mr-2" />
                          Download
                        </Button>
                      </div>
                    </div>
                  </div>
                )}
                <div className="flex justify-end space-x-2 pt-4">
                  <Button variant="outline" className="border-slate-600 text-slate-300 hover:bg-slate-700" onClick={closeDetailsModal}>
                    Close
                  </Button>
                  <Button className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600">
                    Edit Project
                  </Button>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

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
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Stats Cards */}
          <div className="lg:col-span-4 grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
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
                    {tasks.filter(t => t.status === 'running' || t.status === 'processing').length}
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
                  <div className="text-2xl font-bold text-white">
                    {projects.filter(p => p.status === 'completed').length}
                  </div>
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
                  <div className="text-2xl font-bold text-white">94%</div>
                </CardContent>
              </Card>
            </motion.div>
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
                              onClick={() => handleViewDetails(project)}
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
              </TabsContent>

              <TabsContent value="tasks" className="space-y-4">
                <h2 className="text-xl font-semibold text-white">Active Tasks</h2>
                <div className="grid gap-4">
                  {tasks.filter(task => task.status === 'running' || task.status === 'processing').map((task, index) => (
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
          </div>
        </div>
      </main>
    </div>
  )
}

export default Dashboard

