import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, ArrowRight, Video, Zap, Wand2, Play, Settings } from 'lucide-react'
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion'
import ApiService from '../services/api'
import VideoProgressTracker from './VideoProgressTracker'
import '../App.css'

const VideoCreationWizard = ({ onBack }) => {
  const [currentStep, setCurrentStep] = useState(1)
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    prompt: '',
    workflowType: 'assembler',
    duration: '30',
    style: 'professional',
    voiceType: 'female',
    voiceId: null,
    language: 'en',
    orientation: 'landscape',
    width: '1920',
    height: '1080'
  })
  const [voices, setVoices] = useState([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [taskId, setTaskId] = useState(null)

  useEffect(() => {
    let cancelled = false
    ApiService.getVoices()
      .then((data) => {
        if (!cancelled && Array.isArray(data)) {
          setVoices(data)
        }
      })
      .catch((err) => console.error('Failed to load voices:', err))
    return () => {
      cancelled = true
    }
  }, [])

  const totalSteps = 4
  const progress = (currentStep / totalSteps) * 100

  const handleInputChange = (field, value) => {
    // Handle orientation changes to set proper dimensions
    if (field === 'orientation') {
      let width, height;
      switch (value) {
        case 'portrait':
          width = '1080';
          height = '1920';
          break;
        case 'square':
          width = '1080';
          height = '1080';
          break;
        case 'landscape':
        default:
          width = '1920';
          height = '1080';
          break;
      }
      setFormData(prev => ({ 
        ...prev, 
        orientation: value,
        width,
        height
      }));
    } else if (field === 'width' || field === 'height') {
      setFormData(prev => ({ ...prev, [field]: value }));
    } else {
      setFormData(prev => ({ ...prev, [field]: value }));
    }
  }

  const nextStep = () => {
    if (currentStep < totalSteps) {
      setCurrentStep(currentStep + 1)
    }
  }

  const prevStep = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleSubmit = async () => {
    setIsSubmitting(true)
    try {
      // First create a user (for demo purposes, using a default user)
      let user
      try {
        const users = await ApiService.getUsers()
        user = users.length > 0 ? users[0] : null
      } catch {
        // Create a default user if none exists
        user = await ApiService.createUser({
          username: 'demo_user',
          email: 'demo@moneyweaver.com'
        })
      }

      // Create the project
      const project = await ApiService.createProject({
        title: formData.title,
        description: formData.description,
        user_id: user.id,
        workflow_type: formData.workflowType
      })

      // Start video generation based on workflow type
      let response
      if (formData.workflowType === 'assembler') {
        response = await ApiService.generateAssemblerVideo(project.id, formData.prompt, {
          voice_type: formData.voiceType,
          voice_id: formData.voiceId,
          duration: parseInt(formData.duration),
          orientation: formData.orientation,
          width: parseInt(formData.width),
          height: parseInt(formData.height)
        })
      } else {
        response = await ApiService.generateGenerativeVideo(project.id, formData.prompt, {
          voice_id: formData.voiceId
        })
      }

      console.log('Video generation started:', response)
      setTaskId(response.task_id)
      // Don't go back to dashboard immediately, show progress tracker instead
    } catch (error) {
      console.error('Failed to create video:', error)
      alert('Failed to start video creation. Please try again.')
      setIsSubmitting(false)
    }
  }

  const closeProgressTracker = () => {
    setTaskId(null)
    setIsSubmitting(false)
    onBack() // Return to dashboard when progress tracker is closed
  }

  const stepVariants = {
    hidden: { opacity: 0, x: 50 },
    visible: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: -50 }
  }

  // If we have a task ID, show the progress tracker
  if (taskId) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-4">
        <VideoProgressTracker taskId={taskId} onClose={closeProgressTracker} />
      </div>
    )
  }

  // Show submitting state
  if (isSubmitting) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-4">
        <Card className="w-full max-w-md bg-slate-800 border-slate-700">
          <CardHeader>
            <CardTitle className="text-white flex items-center justify-center">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              >
                <Zap className="h-6 w-6 text-yellow-500" />
              </motion.div>
              <span className="ml-2">Starting Video Generation</span>
            </CardTitle>
            <CardDescription className="text-slate-400 text-center">
              Setting up your video project...
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <Progress value={50} className="h-2" />
              <p className="text-center text-slate-300 text-sm">
                Please wait while we initialize your video creation process
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Button variant="outline" onClick={onBack}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Dashboard
              </Button>
              <div>
                <h1 className="text-2xl font-bold text-white">Create New Video</h1>
                <p className="text-sm text-slate-400">Step {currentStep} of {totalSteps}</p>
              </div>
            </div>
            <div className="w-64">
              <Progress value={progress} className="h-2" />
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <div className="max-w-2xl mx-auto">
          <AnimatePresence mode="wait">
            {/* Step 1: Project Details */}
            {currentStep === 1 && (
              <motion.div
                key="step1"
                variants={stepVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                transition={{ duration: 0.3 }}
              >
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardHeader>
                    <CardTitle className="text-white flex items-center">
                      <Settings className="h-5 w-5 mr-2" />
                      Project Details
                    </CardTitle>
                    <CardDescription className="text-slate-400">
                      Set up your video project with basic information
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div className="space-y-2">
                      <Label htmlFor="title" className="text-white">Project Title</Label>
                      <Input
                        id="title"
                        placeholder="Enter your video title..."
                        value={formData.title}
                        onChange={(e) => handleInputChange('title', e.target.value)}
                        className="bg-slate-700 border-slate-600 text-white"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="description" className="text-white">Description</Label>
                      <Textarea
                        id="description"
                        placeholder="Describe your video project..."
                        value={formData.description}
                        onChange={(e) => handleInputChange('description', e.target.value)}
                        className="bg-slate-700 border-slate-600 text-white min-h-[100px]"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="prompt" className="text-white">Video Prompt</Label>
                      <Textarea
                        id="prompt"
                        placeholder="Describe what you want your video to be about..."
                        value={formData.prompt}
                        onChange={(e) => handleInputChange('prompt', e.target.value)}
                        className="bg-slate-700 border-slate-600 text-white min-h-[120px]"
                      />
                      <p className="text-xs text-slate-400">
                        Be specific about the content, style, and tone you want for your video.
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Step 2: Workflow Type */}
            {currentStep === 2 && (
              <motion.div
                key="step2"
                variants={stepVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                transition={{ duration: 0.3 }}
              >
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardHeader>
                    <CardTitle className="text-white flex items-center">
                      <Wand2 className="h-5 w-5 mr-2" />
                      Choose Workflow Type
                    </CardTitle>
                    <CardDescription className="text-slate-400">
                      Select how you want your video to be generated
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <RadioGroup
                      value={formData.workflowType}
                      onValueChange={(value) => handleInputChange('workflowType', value)}
                      className="space-y-4"
                    >
                      <div className="flex items-center space-x-3 p-4 rounded-lg border border-slate-600 hover:border-slate-500 transition-colors">
                        <RadioGroupItem value="assembler" id="assembler" />
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <Video className="h-5 w-5 text-blue-400" />
                            <Label htmlFor="assembler" className="text-white font-medium">
                              Assembler Workflow
                            </Label>
                            <Badge className="bg-blue-500 text-white">Fast</Badge>
                          </div>
                          <p className="text-sm text-slate-400 mt-1">
                            Uses stock footage, AI-generated script, and text-to-speech for quick video creation.
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center space-x-3 p-4 rounded-lg border border-slate-600 hover:border-slate-500 transition-colors">
                        <RadioGroupItem value="generative" id="generative" />
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <Zap className="h-5 w-5 text-purple-400" />
                            <Label htmlFor="generative" className="text-white font-medium">
                              Generative Workflow
                            </Label>
                            <Badge className="bg-purple-500 text-white">AI-Powered</Badge>
                          </div>
                          <p className="text-sm text-slate-400 mt-1">
                            Creates entirely new video content using advanced AI models like ComfyUI.
                          </p>
                        </div>
                      </div>
                    </RadioGroup>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Step 3: Video Settings */}
            {currentStep === 3 && (
              <motion.div
                key="step3"
                variants={stepVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                transition={{ duration: 0.3 }}
              >
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardHeader>
                    <CardTitle className="text-white flex items-center">
                      <Settings className="h-5 w-5 mr-2" />
                      Video Settings
                    </CardTitle>
                    <CardDescription className="text-slate-400">
                      Configure your video parameters
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="duration" className="text-white">Duration (seconds)</Label>
                        <Select value={formData.duration} onValueChange={(value) => handleInputChange('duration', value)}>
                          <SelectTrigger className="bg-slate-700 border-slate-600 text-white">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="15">15 seconds</SelectItem>
                            <SelectItem value="30">30 seconds</SelectItem>
                            <SelectItem value="60">1 minute</SelectItem>
                            <SelectItem value="120">2 minutes</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="style" className="text-white">Video Style</Label>
                        <Select value={formData.style} onValueChange={(value) => handleInputChange('style', value)}>
                          <SelectTrigger className="bg-slate-700 border-slate-600 text-white">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="professional">Professional</SelectItem>
                            <SelectItem value="casual">Casual</SelectItem>
                            <SelectItem value="cinematic">Cinematic</SelectItem>
                            <SelectItem value="educational">Educational</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="orientation" className="text-white">Orientation</Label>
                        <Select value={formData.orientation} onValueChange={(value) => handleInputChange('orientation', value)}>
                          <SelectTrigger className="bg-slate-700 border-slate-600 text-white">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="landscape">Landscape (16:9)</SelectItem>
                            <SelectItem value="portrait">Portrait (9:16)</SelectItem>
                            <SelectItem value="square">Square (1:1)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="resolution" className="text-white">Resolution</Label>
                        <Select value={`${formData.width}x${formData.height}`} onValueChange={(value) => {
                          const [width, height] = value.split('x');
                          handleInputChange('width', width);
                          handleInputChange('height', height);
                        }}>
                          <SelectTrigger className="bg-slate-700 border-slate-600 text-white">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {formData.orientation === 'portrait' ? (
                              <>
                                <SelectItem value="1080x1920">Full HD Portrait (1080x1920)</SelectItem>
                                <SelectItem value="720x1280">HD Portrait (720x1280)</SelectItem>
                                <SelectItem value="480x854">FWVGA Portrait (480x854)</SelectItem>
                              </>
                            ) : formData.orientation === 'square' ? (
                              <>
                                <SelectItem value="1080x1080">Full HD Square (1080x1080)</SelectItem>
                                <SelectItem value="720x720">HD Square (720x720)</SelectItem>
                                <SelectItem value="480x480">FWVGA Square (480x480)</SelectItem>
                              </>
                            ) : (
                              <>
                                <SelectItem value="3840x2160">4K (3840x2160)</SelectItem>
                                <SelectItem value="2560x1440">QHD (2560x1440)</SelectItem>
                                <SelectItem value="1920x1080">Full HD (1920x1080)</SelectItem>
                                <SelectItem value="1280x720">HD (1280x720)</SelectItem>
                                <SelectItem value="854x480">FWVGA (854x480)</SelectItem>
                              </>
                            )}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="voiceType" className="text-white">Voice Type</Label>
                        <Select value={formData.voiceType} onValueChange={(value) => handleInputChange('voiceType', value)}>
                          <SelectTrigger className="bg-slate-700 border-slate-600 text-white">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="female">Female Voice (Standard)</SelectItem>
                            <SelectItem value="male">Male Voice (Standard)</SelectItem>
                            <SelectItem value="af_warm">Female Voice (Warm)</SelectItem>
                            <SelectItem value="af_cool">Female Voice (Cool)</SelectItem>
                            <SelectItem value="af_warm_male">Male Voice (Warm)</SelectItem>
                            <SelectItem value="af_cool_male">Male Voice (Cool)</SelectItem>
                            <SelectItem value="neutral">Neutral Voice</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="language" className="text-white">Language</Label>
                        <Select value={formData.language} onValueChange={(value) => handleInputChange('language', value)}>
                          <SelectTrigger className="bg-slate-700 border-slate-600 text-white">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="en">English</SelectItem>
                            <SelectItem value="es">Spanish</SelectItem>
                            <SelectItem value="fr">French</SelectItem>
                            <SelectItem value="de">German</SelectItem>
                            <SelectItem value="zh">Chinese</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="clonedVoice" className="text-white">Cloned Voice</Label>
                      <Select
                        value={formData.voiceId ? String(formData.voiceId) : 'default'}
                        onValueChange={(value) => handleInputChange('voiceId', value === 'default' ? null : Number(value))}
                      >
                        <SelectTrigger className="bg-slate-700 border-slate-600 text-white">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="default">Default (Kokoro)</SelectItem>
                          {voices.map((voice) => (
                            <SelectItem key={voice.id} value={String(voice.id)}>
                              {voice.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Step 4: Review & Create */}
            {currentStep === 4 && (
              <motion.div
                key="step4"
                variants={stepVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                transition={{ duration: 0.3 }}
              >
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardHeader>
                    <CardTitle className="text-white flex items-center">
                      <Play className="h-5 w-5 mr-2" />
                      Review & Create
                    </CardTitle>
                    <CardDescription className="text-slate-400">
                      Review your settings and start video generation
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div className="space-y-4">
                      <div className="p-4 rounded-lg bg-slate-700/50 border border-slate-600">
                        <h3 className="text-white font-medium mb-2">Project Details</h3>
                        <div className="space-y-1 text-sm">
                          <p className="text-slate-300"><span className="text-slate-400">Title:</span> {formData.title}</p>
                          <p className="text-slate-300"><span className="text-slate-400">Description:</span> {formData.description}</p>
                          <p className="text-slate-300"><span className="text-slate-400">Prompt:</span> {formData.prompt}</p>
                        </div>
                      </div>

                      <div className="p-4 rounded-lg bg-slate-700/50 border border-slate-600">
                        <h3 className="text-white font-medium mb-2">Configuration</h3>
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <p className="text-slate-400">Workflow:</p>
                            <Badge className={formData.workflowType === 'generative' ? 'bg-purple-500' : 'bg-blue-500'}>
                              {formData.workflowType}
                            </Badge>
                          </div>
                          <div>
                            <p className="text-slate-400">Duration:</p>
                            <p className="text-slate-300">{formData.duration} seconds</p>
                          </div>
                          <div>
                            <p className="text-slate-400">Style:</p>
                            <p className="text-slate-300">{formData.style}</p>
                          </div>
                          <div>
                            <p className="text-slate-400">Voice:</p>
                            <p className="text-slate-300">{formData.voiceType}</p>
                          </div>
                          <div>
                            <p className="text-slate-400">Cloned Voice:</p>
                            <p className="text-slate-300">
                              {formData.voiceId
                                ? (voices.find((v) => v.id === formData.voiceId)?.name || `#${formData.voiceId}`)
                                : 'Default (Kokoro)'}
                            </p>
                          </div>
                          <div>
                            <p className="text-slate-400">Orientation:</p>
                            <p className="text-slate-300">{formData.orientation}</p>
                          </div>
                          <div>
                            <p className="text-slate-400">Resolution:</p>
                            <p className="text-slate-300">{formData.width}x{formData.height}</p>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="p-4 rounded-lg bg-blue-900/20 border border-blue-700">
                      <p className="text-blue-200 text-sm">
                        <strong>Estimated processing time:</strong> {formData.workflowType === 'generative' ? '5-15 minutes' : '2-5 minutes'}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Navigation */}
          <div className="flex justify-between mt-8">
            <Button
              variant="outline"
              onClick={prevStep}
              disabled={currentStep === 1}
              className="border-slate-600 text-slate-300 hover:bg-slate-700"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Previous
            </Button>

            {currentStep < totalSteps ? (
              <Button
                onClick={nextStep}
                disabled={!formData.title || !formData.prompt}
                className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
              >
                Next
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            ) : (
              <Button
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600"
              >
                {isSubmitting ? (
                  <>
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                      className="h-4 w-4 mr-2"
                    >
                      <Zap className="h-4 w-4" />
                    </motion.div>
                    Creating...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    Create Video
                  </>
                )}
              </Button>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

export default VideoCreationWizard

