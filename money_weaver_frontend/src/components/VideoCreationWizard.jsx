import { useState, useEffect, useMemo } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { ArrowLeft, ArrowRight, Video, Zap, Play, Settings, PenLine, Film, Mic, Check, Dices, Search, Sparkles } from 'lucide-react'
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion'
import { toast } from 'sonner'
import ApiService from '../services/api'
import EnhanceButton from './EnhanceButton'
import { useAuthStore } from '@/store/authStore'
import VideoProgressTracker from './VideoProgressTracker'
import ScriptEditor from './ScriptEditor'
import Storyboard from './Storyboard'
import ModelPicker from './ModelPicker'
import { useModels } from '@/hooks/useModels'
import { usePresets } from '@/hooks/usePresets'
import { useVoices } from '@/hooks/useVoices'
import { useNiches } from '@/hooks/useNiches'
import { parseScriptText } from '@/lib/scriptParser'
import '../App.css'

const STEPS = [
  { id: 1, label: 'Script', icon: PenLine },
  { id: 2, label: 'Storyboard', icon: Film },
  { id: 3, label: 'Preset & Voice', icon: Mic },
  { id: 4, label: 'Review & Generate', icon: Play },
]

// Plain-text script -> editor HTML. Bold **Scene N** lines become <strong> paragraphs;
// everything else becomes a plain paragraph. Input is HTML-escaped.
const scriptTextToHtml = (text) => {
  const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;')
  const html = (text || '')
    .split(/\n/)
    .filter((line) => line.trim())
    .map((line) =>
      /^\*\*.*\*\*$/.test(line.trim())
        ? `<p><strong>${line.trim().slice(2, -2)}</strong></p>`
        : `<p>${line.trim()}</p>`,
    )
    .join('')
  return html ? `<div>${html}</div>` : ''
}

const VideoCreationWizard = ({ onBack }) => {
  const [currentStep, setCurrentStep] = useState(1)
  const [visitedSteps, setVisitedSteps] = useState(new Set([1]))
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    prompt: '',
    scriptHtml: '',
    workflowType: 'assembler',
    presetId: null,
    duration: '30',
    voiceType: 'female',
    voiceId: null,
    language: 'en',
    orientation: 'landscape',
    width: '1920',
    height: '1080',
    nicheId: ''
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [taskId, setTaskId] = useState(null)
  const [randomIdea, setRandomIdea] = useState(null)
  const [discoveredTopics, setDiscoveredTopics] = useState([])
  const [isDiscovering, setIsDiscovering] = useState(false)
  const [isDrafting, setIsDrafting] = useState(false)
  const [showModelOverrides, setShowModelOverrides] = useState(false)
  const [modelOverrides, setModelOverrides] = useState({ idea: null, script: null, videoGen: null })
  // Wizard-session voice model override (fal model id). Display-only for now —
  // backend task consumption of voice_tts assignments already exists.
  const [voiceModelOverride, setVoiceModelOverride] = useState(null)

  const modelsQuery = useModels()
  const presetsQuery = usePresets()
  const voicesQuery = useVoices()
  const nichesQuery = useNiches()
  const presets = presetsQuery.data ?? []
  const voices = voicesQuery.data ?? []
  const niches = nichesQuery.data ?? []
  const models = modelsQuery.data?.models ?? []
  const presetsLoading = presetsQuery.isLoading
  const voicesLoading = voicesQuery.isLoading

  const { scenes } = parseScriptText(formData.prompt)
  const selectedPreset = presets.find((p) => p.id === formData.presetId) ?? null
  const apiVoiceModels = useMemo(
    () => (modelsQuery.data?.models ?? []).filter((m) => m?.kind === 'voice'),
    [modelsQuery.data],
  )

  // Read-only label for the video_gen assignment (Settings > Model Assignments).
  const formatVideoGenTarget = (assignmentId) => {
    if (!assignmentId) return 'Auto'
    if (assignmentId === 'comfy_local') return 'ComfyUI (local)'
    if (assignmentId.startsWith('fal-ai/')) {
      const match = models.find((m) => m?.id === assignmentId)
      const label = match?.label || match?.display_name || assignmentId
      return `fal · ${label}`
    }
    return 'Auto'
  }

  useEffect(() => {
    if (presetsQuery.isError) {
      toast.error('Failed to load presets', {
        id: 'wizard-presets-error',
        description: presetsQuery.error?.message,
      })
    }
  }, [presetsQuery.isError, presetsQuery.error])

  useEffect(() => {
    if (voicesQuery.isError) {
      toast.error('Failed to load voices', {
        id: 'wizard-voices-error',
        description: voicesQuery.error?.message,
      })
    }
  }, [voicesQuery.isError, voicesQuery.error])

  useEffect(() => {
    if (nichesQuery.isError) {
      toast.error('Failed to load niches', {
        id: 'wizard-niches-error',
        description: nichesQuery.error?.message,
      })
    }
  }, [nichesQuery.isError, nichesQuery.error])

  useEffect(() => {
    let cancelled = false
    ApiService.getModelAssignments()
      .then((data) => {
        if (cancelled) return
        setModelOverrides({
          idea: data?.assignments?.idea ?? null,
          script: data?.assignments?.script ?? null,
          videoGen: data?.assignments?.video_gen ?? null,
        })
      })
      .catch((error) => console.error('Failed to load model assignments:', error))
    return () => {
      cancelled = true
    }
  }, [])

  const handleDiscoverTopics = async () => {
    if (!formData.nicheId) return
    setIsDiscovering(true)
    try {
      const result = await ApiService.fetchTopics(formData.nicheId, 20)
      setDiscoveredTopics(result?.topics ?? [])
    } catch (error) {
      console.error('Failed to discover topics:', error)
      toast.error('Failed to discover topics. Please try again.')
    } finally {
      setIsDiscovering(false)
    }
  }

  const handleTopicSelect = (topic) => {
    setFormData(prev => ({
      ...prev,
      title: prev.title || topic.title,
      prompt: topic.title,
    }))
  }

  const totalSteps = STEPS.length

  const handleInputChange = (field, value) => {
    if (field === 'orientation') {
      let width, height
      switch (value) {
        case 'portrait':
          width = '1080'
          height = '1920'
          break
        case 'square':
          width = '1080'
          height = '1080'
          break
        case 'landscape':
        default:
          width = '1920'
          height = '1080'
          break
      }
      setFormData(prev => ({
        ...prev,
        orientation: value,
        width,
        height
      }))
    } else {
      setFormData(prev => ({ ...prev, [field]: value }))
    }
  }

  const handlePresetChange = (presetId) => {
    const preset = presets.find((p) => p.id === Number(presetId))
    if (!preset) return
    const orientation = preset.width > preset.height
      ? 'landscape'
      : preset.width < preset.height
        ? 'portrait'
        : 'square'
    setFormData(prev => ({
      ...prev,
      presetId: preset.id,
      width: String(preset.width),
      height: String(preset.height),
      orientation,
      duration: String(preset.duration_min),
    }))
  }

  const handleScriptChange = (html, text) => {
    setFormData(prev => ({ ...prev, scriptHtml: html, prompt: text }))
  }

  // Keep editor + prompt in sync when the prompt text is replaced externally.
  const handleEnhancedPrompt = (text) => {
    handleScriptChange(scriptTextToHtml(text), text)
  }

  const hasTopic = Boolean(formData.prompt.trim() || formData.title.trim())

  const handleDraftScript = async () => {
    const topic = formData.prompt.trim() || formData.title.trim()
    if (!topic || isDrafting) return
    if (formData.scriptHtml && !window.confirm('Replace the current script with a generated draft?')) return
    setIsDrafting(true)
    try {
      const result = await ApiService.draftScript({
        topic,
        duration: parseInt(formData.duration),
        niche_id: formData.nicheId || undefined,
      })
      const script = result?.script ?? ''
      handleScriptChange(scriptTextToHtml(script), script)
    } catch (error) {
      console.error('Failed to draft script:', error)
      toast.error(error.message || 'Failed to draft script')
    } finally {
      setIsDrafting(false)
    }
  }

  const canProceed = () => {
    if (currentStep === 1) return Boolean(formData.title.trim() && formData.prompt.trim())
    if (currentStep === 2) return scenes.length > 0
    if (currentStep === 3) return presets.length === 0 || Boolean(selectedPreset)
    return true
  }

  const canGenerate = Boolean(formData.prompt.trim()) && (presets.length === 0 || Boolean(selectedPreset))

  const nextStep = () => {
    if (!canProceed()) return
    if (currentStep < totalSteps) {
      const next = currentStep + 1
      setVisitedSteps(prev => new Set(prev).add(next))
      setCurrentStep(next)
    }
  }

  const prevStep = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1)
    }
  }

  const goToStep = (step) => {
    if (visitedSteps.has(step)) {
      setCurrentStep(step)
    }
  }

  const handleSubmit = async () => {
    setIsSubmitting(true)
    try {
      const currentUser = useAuthStore.getState().user
      if (!currentUser?.id) {
        toast.error('You must be logged in to create a video')
        setIsSubmitting(false)
        return
      }

      // Create the project
      const project = await ApiService.createProject({
        title: formData.title,
        description: formData.description,
        user_id: currentUser.id,
        workflow_type: formData.workflowType
      })

      // Start video generation based on workflow type
      let response
      if (formData.workflowType === 'assembler') {
        response = await ApiService.generateAssemblerVideo(project.id, formData.prompt, {
          voice_type: formData.voiceType,
          voice_id: formData.voiceId,
          voice_override: voiceModelOverride || undefined,
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

      setTaskId(response.task_id)
      // Don't go back to dashboard immediately, show progress tracker instead
    } catch (error) {
      console.error('Failed to create video:', error)
      toast.error('Failed to start video creation. Please try again.')
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
              <div className="h-2 rounded-full bg-slate-700 overflow-hidden">
                <div className="h-full w-1/2 bg-purple-500 rounded-full" />
              </div>
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
          <div className="flex items-center justify-between mb-4">
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
          </div>
          {/* Step indicators */}
          <div className="flex items-center gap-2 flex-wrap">
            {STEPS.map((step) => {
              const Icon = step.icon
              const active = currentStep === step.id
              const visited = visitedSteps.has(step.id)
              const complete = visited && step.id < currentStep
              return (
                <button
                  key={step.id}
                  type="button"
                  onClick={() => goToStep(step.id)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                    active
                      ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white'
                      : visited
                        ? 'bg-slate-700 text-slate-200 hover:bg-slate-600 cursor-pointer'
                        : 'bg-slate-800/60 text-slate-500 cursor-default'
                  }`}
                  disabled={!visited}
                >
                  {complete ? <Check className="h-3.5 w-3.5" /> : <Icon className="h-3.5 w-3.5" />}
                  <span className="hidden sm:inline">{step.label}</span>
                </button>
              )
            })}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <div className="max-w-2xl mx-auto">
          <AnimatePresence mode="wait">
            {/* Step 1: Write Script */}
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
                      <PenLine className="h-5 w-5 mr-2" />
                      Write Your Script
                    </CardTitle>
                    <CardDescription className="text-slate-400">
                      Start from the script — your storyboard is generated from it.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div className="grid grid-cols-1 gap-4">
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
                        <div className="flex items-center justify-between">
                          <Label htmlFor="script" className="text-white">Video Script</Label>
                          <EnhanceButton
                            text={formData.prompt}
                            onEnhanced={handleEnhancedPrompt}
                            label="Enhance prompt"
                          />
                        </div>
                        <ScriptEditor
                          value={formData.scriptHtml}
                          onChange={handleScriptChange}
                          placeholder="Write your script. Make scene headers bold — e.g. **Scene 1: Intro (0s-5s)** — each followed by a Voiceover: &quot;...&quot; line to structure your storyboard."
                        />
                        <p className="text-xs text-slate-400">
                          Be specific about the content, style, and tone you want for your video. Scene headers are parsed into the storyboard in the next step.
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Randomize topic button in step 1 */}
            {currentStep === 1 && (
              <motion.div
                key="randomize-topic"
                variants={stepVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                transition={{ duration: 0.3 }}
              >
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardHeader>
                    <CardTitle className="text-white flex items-center">
                      <Dices className="h-5 w-5 mr-2" />
                      Randomize Topic
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-slate-400">
                      Generate a random topic and script prompt.
                    </p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={async () => {
                          setIsSubmitting(true)
                          try {
                            const result = await ApiService.randomIdea(
                              modelOverrides.idea ? { model: modelOverrides.idea } : {}
                            )
                            setRandomIdea(result)
                            setFormData(prev => ({
                              ...prev,
                              title: result.title,
                              prompt: result.topic
                            }))
                          } catch (error) {
                            console.error('Failed to randomize topic:', error)
                            toast.error('Failed to randomize topic')
                          } finally {
                            setIsSubmitting(false)
                          }
                        }}
                      >
                        Randomize
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleDraftScript}
                        disabled={!hasTopic || isDrafting}
                      >
                        <Sparkles className="h-4 w-4 mr-2" />
                        {isDrafting ? 'Drafting...' : 'Draft Script'}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Advanced: inline model overrides in step 1 */}
            {currentStep === 1 && (
              <motion.div
                key="model-overrides"
                variants={stepVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                transition={{ duration: 0.3 }}
              >
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardContent className="p-4 space-y-3">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      aria-expanded={showModelOverrides}
                      onClick={() => setShowModelOverrides((v) => !v)}
                    >
                      <Settings className="h-4 w-4 mr-2" />
                      Advanced: model overrides
                    </Button>
                    {showModelOverrides && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <Label htmlFor="idea-model" className="text-white">Idea model</Label>
                          <ModelPicker
                            models={models}
                            value={modelOverrides.idea}
                            onChange={(id) => setModelOverrides((prev) => ({ ...prev, idea: id }))}
                            kinds={['text']}
                            compact
                          />
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor="script-model" className="text-white">Script model</Label>
                          <ModelPicker
                            models={models}
                            value={modelOverrides.script}
                            onChange={(id) => setModelOverrides((prev) => ({ ...prev, script: id }))}
                            kinds={['text']}
                            compact
                          />
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Niche + topic discovery in step 1 */}
            {currentStep === 1 && (
              <motion.div
                key="topic-discovery"
                variants={stepVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                transition={{ duration: 0.3 }}
              >
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardHeader>
                    <CardTitle className="text-white flex items-center">
                      <Search className="h-5 w-5 mr-2" />
                      Discover Topics
                    </CardTitle>
                    <CardDescription className="text-slate-400">
                      Pick a niche and discover trending topics to write about.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label className="text-white">Niche</Label>
                      <Select
                        value={formData.nicheId || 'none'}
                        onValueChange={(value) => {
                          handleInputChange('nicheId', value === 'none' ? '' : value)
                          setDiscoveredTopics([])
                        }}
                      >
                        <SelectTrigger className="bg-slate-700 border-slate-600 text-white">
                          <SelectValue placeholder="Select a niche..." />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">Select a niche...</SelectItem>
                          {niches.map((niche) => (
                            <SelectItem key={niche} value={niche}>
                              {niche}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleDiscoverTopics}
                      disabled={!formData.nicheId || isDiscovering}
                    >
                      {isDiscovering ? 'Discovering...' : 'Discover topics'}
                    </Button>
                    {discoveredTopics.length > 0 && (
                      <div className="grid gap-2">
                        {discoveredTopics.map((topic) => (
                          <button
                            key={`${topic.source}-${topic.url}`}
                            type="button"
                            onClick={() => handleTopicSelect(topic)}
                            className="text-left p-3 rounded-lg bg-slate-700/40 border border-slate-600 hover:border-purple-500 transition-colors"
                          >
                            <p className="text-sm text-white font-medium">{topic.title}</p>
                            <p className="text-xs text-slate-400 mt-1">
                              {topic.source}
                              {topic.url ? ` · ${topic.url}` : ''}
                            </p>
                          </button>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Step 2: Storyboard */}
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
                      <Film className="h-5 w-5 mr-2" />
                      Storyboard Preview
                    </CardTitle>
                    <CardDescription className="text-slate-400">
                      Review how your script splits into scenes before configuring output.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <Storyboard text={formData.prompt} />
                    {randomIdea && (
                      <p className="text-xs text-amber-400">
                        Randomized idea: <strong>{randomIdea.title}</strong> — {randomIdea.topic}
                      </p>
                    )}
                    {scenes.length === 0 && (
                      <p className="text-xs text-amber-400">
                        No scenes parsed. Go back and add bold{' '}
                        <code className="text-purple-300">**Scene N: Title (0s-5s)**</code> headers to your script.
                      </p>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Step 3: Preset & Voice */}
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
                      Output & Voice
                    </CardTitle>
                    <CardDescription className="text-slate-400">
                      Pick a preset and configure your video parameters
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div className="space-y-2">
                      <Label className="text-white">Workflow Type</Label>
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
                      <p
                        data-testid="video-generation-target"
                        className="text-xs text-slate-400"
                      >
                        Video generation: {formatVideoGenTarget(modelOverrides.videoGen)}
                      </p>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="preset" className="text-white">Format Preset</Label>
                      {presetsLoading ? (
                        <Skeleton className="h-10 w-full" />
                      ) : presets.length === 0 ? (
                        <p className="text-sm text-slate-400 p-3 rounded-lg bg-slate-700/40 border border-slate-600">
                          No presets available. Configure manually below.
                        </p>
                      ) : (
                        <Select
                          value={formData.presetId ? String(formData.presetId) : 'none'}
                          onValueChange={handlePresetChange}
                        >
                          <SelectTrigger className="bg-slate-700 border-slate-600 text-white">
                            <SelectValue placeholder="Select a preset..." />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="none">Select a preset...</SelectItem>
                            {presets.map((preset) => (
                              <SelectItem key={preset.id} value={String(preset.id)}>
                                {preset.name} ({preset.platform}) — {preset.width}x{preset.height} {preset.fps}fps
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                      {selectedPreset && (
                        <p className="text-xs text-slate-400">
                          Preset applied: {selectedPreset.width}x{selectedPreset.height}, {selectedPreset.duration_min}-
                          {selectedPreset.duration_max}s target duration. Adjust below if needed.
                        </p>
                      )}
                    </div>

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
                          const [width, height] = value.split('x')
                          handleInputChange('width', width)
                          handleInputChange('height', height)
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
                        <Label htmlFor="clonedVoice" className="text-white">Cloned Voice</Label>
                        {voicesLoading ? (
                          <Skeleton className="h-10 w-full" />
                        ) : (
                          <Select
                            value={formData.voiceId && voices.some((v) => v.id === formData.voiceId) ? String(formData.voiceId) : 'default'}
                            onValueChange={(value) => handleInputChange('voiceId', value === 'default' ? null : Number(value))}
                          >
                            <SelectTrigger className="bg-slate-700 border-slate-600 text-white">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="default">Default (Kokoro)</SelectItem>
                              {voices.length === 0 && (
                                <SelectItem value="none" disabled>No cloned voices</SelectItem>
                              )}
                              {voices.map((voice) => (
                                <SelectItem key={voice.id} value={String(voice.id)}>
                                  {voice.name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label className="text-white">API Voices</Label>
                      {apiVoiceModels.length === 0 ? (
                        <p className="text-sm text-slate-400 p-3 rounded-lg bg-slate-700/40 border border-slate-600">
                          No API voices available from your configured providers.
                        </p>
                      ) : (
                        <div className="grid gap-2">
                          {apiVoiceModels.map((model) => {
                            const active = voiceModelOverride === model.id
                            return (
                              <button
                                key={model.id}
                                type="button"
                                aria-pressed={active}
                                onClick={() => setVoiceModelOverride(active ? null : model.id)}
                                className={`flex items-center justify-between gap-3 text-left p-3 rounded-lg border transition-colors ${
                                  active
                                    ? 'border-purple-500 bg-purple-900/30'
                                    : 'border-slate-600 hover:border-slate-500'
                                }`}
                              >
                                <span className="min-w-0">
                                  <span className="block truncate text-sm text-white font-medium">
                                    {model.label || model.display_name || model.id}
                                  </span>
                                  {model.provider && (
                                    <span className="block truncate text-xs text-slate-400">{model.provider}</span>
                                  )}
                                </span>
                                <Badge className="shrink-0 bg-indigo-500 text-white">API</Badge>
                              </button>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Step 4: Review & Generate */}
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
                      Review & Generate
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
                          <p className="text-slate-300"><span className="text-slate-400">Script:</span> {formData.prompt}</p>
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
                            <p className="text-slate-400">Preset:</p>
                            <p className="text-slate-300">{selectedPreset ? selectedPreset.name : 'None selected'}</p>
                          </div>
                          <div>
                            <p className="text-slate-400">Duration:</p>
                            <p className="text-slate-300">{formData.duration} seconds</p>
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
                          <div>
                            <p className="text-slate-400">Language:</p>
                            <p className="text-slate-300">{formData.language}</p>
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
                disabled={!canProceed()}
                className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
              >
                Next
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            ) : (
              <Button
                onClick={handleSubmit}
                disabled={isSubmitting || !canGenerate}
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