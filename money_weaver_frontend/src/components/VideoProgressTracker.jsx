import { useState, useEffect } from 'react'
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useTaskStatus } from '@/hooks/useTaskStatus'
import { 
  Settings, 
  FileText, 
  Mic, 
  Video, 
  Zap, 
  Play, 
  CheckCircle, 
  Clock, 
  AlertCircle,
  X
} from 'lucide-react'

const VideoProgressTracker = ({ taskId, onClose }) => {
  const [progress, setProgress] = useState({
    state: 'PENDING',
    current: 0,
    total: 100,
    status: 'Initializing...',
    steps: [
      { id: 'init', name: 'Initializing', status: 'pending', description: 'Setting up video generation' },
      { id: 'script', name: 'Script Generation', status: 'pending', description: 'Creating your video script' },
      { id: 'voiceover', name: 'Voiceover Generation', status: 'pending', description: 'Generating audio narration' },
      { id: 'footage', name: 'Stock Footage', status: 'pending', description: 'Finding relevant video clips' },
      { id: 'assembly', name: 'Video Assembly', status: 'pending', description: 'Combining clips and audio' },
      { id: 'complete', name: 'Complete', status: 'pending', description: 'Finalizing your video' }
    ]
  })

  const [error, setError] = useState(null)

  const { status } = useTaskStatus(taskId, true, 3000)

  useEffect(() => {
    if (!status) return

    // Update overall progress
    setProgress(prev => ({
      ...prev,
      state: status.status === 'completed' ? 'SUCCESS' : status.status === 'failed' ? 'FAILURE' : 'PROGRESS',
      current: status.progress || 0,
      total: 100,
      status: status.message || (status.status === 'completed' ? 'Video generation completed successfully!' : 'Processing...')
    }))

    // Update step statuses based on progress
    setProgress(prev => {
      const steps = [...prev.steps]
      const progressPercent = status.progress || 0
      
      // Update step statuses based on progress percentage
      if (progressPercent >= 0) steps[0].status = 'completed' // Init
      if (progressPercent >= 10) steps[1].status = 'completed' // Script
      if (progressPercent >= 20) steps[1].status = 'completed'
      if (progressPercent >= 30) steps[2].status = 'completed' // Voiceover
      if (progressPercent >= 40) steps[2].status = 'completed'
      if (progressPercent >= 50) steps[3].status = 'completed' // Stock footage
      if (progressPercent >= 70) steps[3].status = 'completed'
      if (progressPercent >= 80) steps[4].status = 'in-progress' // Assembly
      if (progressPercent >= 90) steps[4].status = 'completed'
      if (progressPercent >= 100) {
        steps[4].status = 'completed'
        steps[5].status = 'completed' // Complete
      }
      
      // Mark current step as in-progress
      if (progressPercent >= 10 && progressPercent < 30) steps[1].status = 'in-progress'
      else if (progressPercent >= 30 && progressPercent < 50) steps[2].status = 'in-progress'
      else if (progressPercent >= 50 && progressPercent < 80) steps[3].status = 'in-progress'
      else if (progressPercent >= 80 && progressPercent < 100) steps[4].status = 'in-progress'
      
      return { ...prev, steps }
    })

    // Handle completion / failure
    if (status.status === 'completed') {
      setTimeout(() => {
        setProgress(prev => ({
          ...prev,
          state: 'SUCCESS',
          current: 100,
          status: 'Video generation completed successfully!'
        }))
        setProgress(prev => ({
          ...prev,
          steps: prev.steps.map(step => ({ ...step, status: 'completed' }))
        }))
      }, 1000)
    } else if (status.status === 'failed') {
      setError(status.error || 'Video generation failed')
      setProgress(prev => ({
        ...prev,
        state: 'FAILURE',
        status: status.error || 'Video generation failed'
      }))
    }
  }, [status])

  const getStepIcon = (step) => {
    switch (step.id) {
      case 'init': return <Settings className="h-5 w-5" />
      case 'script': return <FileText className="h-5 w-5" />
      case 'voiceover': return <Mic className="h-5 w-5" />
      case 'footage': return <Video className="h-5 w-5" />
      case 'assembly': return <Zap className="h-5 w-5" />
      case 'complete': return <Play className="h-5 w-5" />
      default: return <Clock className="h-5 w-5" />
    }
  }

  const getStepStatusIcon = (status) => {
    switch (status) {
      case 'completed': return <CheckCircle className="h-5 w-5 text-green-500" />
      case 'in-progress': return <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: "linear" }}><Zap className="h-5 w-5 text-yellow-500" /></motion.div>
      case 'pending': return <Clock className="h-5 w-5 text-gray-400" />
      case 'error': return <AlertCircle className="h-5 w-5 text-red-500" />
      default: return <Clock className="h-5 w-5 text-gray-400" />
    }
  }

  const getStepStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'border-green-500 bg-green-500/10'
      case 'in-progress': return 'border-yellow-500 bg-yellow-500/10'
      case 'pending': return 'border-gray-500 bg-gray-500/10'
      case 'error': return 'border-red-500 bg-red-500/10'
      default: return 'border-gray-500 bg-gray-500/10'
    }
  }

  if (error) {
    return (
      <Card className="w-full max-w-2xl bg-slate-800 border-slate-700">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-white flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-red-500" />
              Error Tracking Progress
            </CardTitle>
            <CardDescription className="text-slate-400">
              Something went wrong while tracking your video generation
            </CardDescription>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent>
          <div className="p-4 rounded-lg bg-red-900/20 border border-red-700">
            <p className="text-red-200">{error}</p>
          </div>
          <div className="mt-4 flex justify-end">
            <Button onClick={onClose}>Close</Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="w-full max-w-2xl bg-slate-800 border-slate-700">
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="text-white flex items-center gap-2">
            <motion.div animate={{ rotate: progress.state === 'PROGRESS' ? 360 : 0 }} transition={{ duration: 1, repeat: progress.state === 'PROGRESS' ? Infinity : 0, ease: "linear" }}>
              <Zap className="h-5 w-5 text-yellow-500" />
            </motion.div>
            Video Generation Progress
          </CardTitle>
          <CardDescription className="text-slate-400">
            Tracking your video creation in real-time
          </CardDescription>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Overall Progress */}
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <span className="text-sm font-medium text-white">{progress.status}</span>
            <Badge variant="secondary" className="bg-slate-700 text-slate-200">
              {Math.round((progress.current / progress.total) * 100)}%
            </Badge>
          </div>
          <Progress 
            value={(progress.current / progress.total) * 100} 
            className="h-2" 
          />
        </div>

        {/* Step-by-step Progress */}
        <div className="space-y-3">
          {progress.steps.map((step, index) => (
            <motion.div
              key={step.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <div className={`flex items-center p-3 rounded-lg border ${getStepStatusColor(step.status)}`}>
                <div className="flex items-center justify-center w-10 h-10 rounded-full bg-slate-700 mr-3">
                  {getStepIcon(step)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <h3 className="font-medium text-white truncate">{step.name}</h3>
                    <div className="flex items-center">
                      {getStepStatusIcon(step.status)}
                    </div>
                  </div>
                  <p className="text-sm text-slate-400 truncate">{step.description}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Completion Message */}
        <AnimatePresence>
          {progress.state === 'SUCCESS' && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="p-4 rounded-lg bg-green-900/20 border border-green-700 text-center"
            >
              <CheckCircle className="h-12 w-12 text-green-500 mx-auto mb-2" />
              <h3 className="text-lg font-medium text-white mb-1">Video Generation Complete!</h3>
              <p className="text-green-200 mb-4">Your video has been successfully created.</p>
              {status?.video_url && (
                <video
                  src={status.video_url}
                  controls
                  className="mx-auto max-w-full rounded-lg border border-green-700"
                />
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Failure Message */}
        <AnimatePresence>
          {progress.state === 'FAILURE' && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="p-4 rounded-lg bg-red-900/20 border border-red-700 text-center"
            >
              <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-2" />
              <h3 className="text-lg font-medium text-white mb-1">Generation Failed</h3>
              <p className="text-red-200">{progress.status}</p>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  )
}

export default VideoProgressTracker