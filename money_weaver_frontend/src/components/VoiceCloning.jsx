import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { Upload, Mic, Play, Square, Trash2 } from 'lucide-react'
import ApiService from '../services/api'

const VoiceCloning = () => {
  const [referenceAudio, setReferenceAudio] = useState(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [consent, setConsent] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [voices, setVoices] = useState([])
  const [loadingVoices, setLoadingVoices] = useState(true)
  const [error, setError] = useState(null)
  const [playingVoiceId, setPlayingVoiceId] = useState(null)
  const audioRef = useRef(null)

  const fetchVoices = async () => {
    setLoadingVoices(true)
    setError(null)
    try {
      const data = await ApiService.getVoices()
      setVoices(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoadingVoices(false)
    }
  }

  useEffect(() => {
    fetchVoices()
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
      }
    }
  }, [])

  const handleFileUpload = (event) => {
    const file = event.target.files[0]
    if (file) {
      setReferenceAudio(file)
    }
  }

  const stopPlayback = () => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    setPlayingVoiceId(null)
  }

  const handlePreviewVoice = async (voice) => {
    if (playingVoiceId === voice.id) {
      stopPlayback()
      return
    }
    stopPlayback()
    try {
      const { preview_url } = await ApiService.previewVoice(voice.id, '')
      const url = ApiService.getAuthedAssetUrl(preview_url)
      const audio = new Audio(url)
      audioRef.current = audio
      setPlayingVoiceId(voice.id)
      audio.play().catch(() => {
        setPlayingVoiceId(null)
        audioRef.current = null
      })
      audio.onended = stopPlayback
    } catch (err) {
      setPlayingVoiceId(null)
      alert(`Preview failed: ${err.message}`)
    }
  }

  const handleDeleteVoice = async (voice) => {
    if (!window.confirm(`Delete voice "${voice.name}"? This cannot be undone.`)) {
      return
    }
    try {
      await ApiService.deleteVoice(voice.id)
      setVoices((prev) => prev.filter((v) => v.id !== voice.id))
      if (playingVoiceId === voice.id) {
        stopPlayback()
      }
    } catch (err) {
      alert(`Delete failed: ${err.message}`)
    }
  }

  const handleCreateVoice = async () => {
    if (!referenceAudio) {
      alert('Please provide reference audio (WAV or MP3, 3-20s, >=16kHz)')
      return
    }
    if (!name.trim()) {
      alert('Please enter a voice name')
      return
    }
    if (!consent) {
      alert('Please confirm you own the rights to this voice')
      return
    }

    const formData = new FormData()
    formData.append('name', name.trim())
    formData.append('reference_audio', referenceAudio)
    if (description.trim()) {
      formData.append('description', description.trim())
    }
    formData.append('consent', 'true')

    setIsUploading(true)
    setError(null)
    try {
      await ApiService.createVoice(formData)
      setName('')
      setDescription('')
      setReferenceAudio(null)
      setConsent(false)
      await fetchVoices()
    } catch (err) {
      setError(err.message)
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-6">
      <div className="max-w-4xl mx-auto">
        <Card className="bg-slate-800/50 border-slate-700">
          <CardHeader>
            <CardTitle className="text-white flex items-center">
              <Mic className="h-5 w-5 mr-2" />
              Voice Cloning
            </CardTitle>
            <CardDescription className="text-slate-400">
              Clone a voice from a reference clip, preview it, and use it when creating videos
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Upload Form */}
            <div className="space-y-4 p-4 rounded-lg bg-slate-700/50 border border-slate-600">
              <h3 className="text-lg font-medium text-white">Create a Cloned Voice</h3>
              <div className="space-y-2">
                <Label htmlFor="voice-name" className="text-white">Voice Name</Label>
                <Input
                  id="voice-name"
                  placeholder="e.g. My Narration Voice"
                  value={name}
                  maxLength={100}
                  onChange={(e) => setName(e.target.value)}
                  className="bg-slate-700 border-slate-600 text-white"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="audio-upload" className="text-white">Reference Audio (WAV/MP3, 3-20s)</Label>
                <Input
                  id="audio-upload"
                  type="file"
                  accept=".wav,.mp3,audio/wav,audio/mpeg"
                  onChange={handleFileUpload}
                  className="bg-slate-700 border-slate-600 text-white file:bg-slate-600 file:text-white"
                />
                {referenceAudio && (
                  <p className="text-sm text-slate-400">Selected: {referenceAudio.name}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="voice-description" className="text-white">Description (optional)</Label>
                <Textarea
                  id="voice-description"
                  placeholder="Describe the voice for your own reference..."
                  value={description}
                  maxLength={300}
                  onChange={(e) => setDescription(e.target.value)}
                  className="bg-slate-700 border-slate-600 text-white min-h-[80px]"
                />
              </div>

              <div className="flex items-start space-x-3 p-3 rounded-lg bg-slate-800/50 border border-slate-600">
                <Checkbox
                  id="consent"
                  checked={consent}
                  onCheckedChange={(checked) => setConsent(checked === true)}
                  className="mt-0.5"
                />
                <Label htmlFor="consent" className="text-slate-300 text-sm leading-relaxed">
                  I confirm that I own or have full rights to this voice, and consent to it being
                  reproduced synthetically.
                </Label>
              </div>

              {error && (
                <p className="text-sm text-red-400">{error}</p>
              )}

              <Button
                onClick={handleCreateVoice}
                disabled={isUploading}
                className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
              >
                {isUploading ? (
                  <>
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent mr-2"></div>
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4 mr-2" />
                    Create Voice
                  </>
                )}
              </Button>

              <p className="text-xs text-slate-500">
                Reference audio must be WAV or MP3, 3-20 seconds long, at least 16kHz, and under 25MB.
              </p>
            </div>

            {/* Voice Library */}
            <div className="p-4 rounded-lg bg-slate-700/50 border border-slate-600">
              <h3 className="text-white font-medium mb-2">Your Voices</h3>
              {loadingVoices ? (
                <p className="text-sm text-slate-400">Loading your voices...</p>
              ) : voices.length === 0 ? (
                <p className="text-sm text-slate-400">
                  No cloned voices yet. Upload a reference clip above to create one.
                </p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {voices.map((voice) => (
                    <div key={voice.id} className="p-3 rounded bg-slate-600/50 border border-slate-500">
                      <div className="flex items-center justify-between space-x-2">
                        <div className="min-w-0">
                          <p className="text-white text-sm font-medium truncate">{voice.name}</p>
                          <p className="text-xs text-slate-400">
                            Created {new Date(voice.created_at).toLocaleDateString()}
                            {voice.description ? ' · ' + voice.description : ''}
                          </p>
                        </div>
                        <div className="flex items-center space-x-1 shrink-0">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-8 px-2 text-slate-400 hover:text-white"
                            onClick={() => handlePreviewVoice(voice)}
                            title={playingVoiceId === voice.id ? 'Stop preview' : 'Preview voice'}
                          >
                            {playingVoiceId === voice.id ? (
                              <Square className="h-4 w-4" />
                            ) : (
                              <Play className="h-4 w-4" />
                            )}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-8 px-2 text-slate-400 hover:text-red-400"
                            onClick={() => handleDeleteVoice(voice)}
                            title="Delete voice"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default VoiceCloning