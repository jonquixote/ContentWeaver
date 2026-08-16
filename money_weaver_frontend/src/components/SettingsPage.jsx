import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Save, Palette, Bell, Shield, Database, Cloud, Plus, Trash2, Check, X, Cpu, Key } from 'lucide-react'
import api from '@/services/api'
import { useAuthStore } from '@/store/authStore'

const passwordSchema = z
  .object({
    current: z.string().min(1, 'Current password is required'),
    new: z.string().min(6, 'New password must be at least 6 characters'),
    confirm: z.string().min(1, 'Please confirm your new password'),
  })
  .refine((d) => d.new === d.confirm, {
    message: 'New passwords do not match',
    path: ['confirm'],
  })

const SettingsPage = () => {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const [settings, setSettings] = useState({
    theme: 'dark',
    notifications: true,
    autoSave: true,
    language: 'en',
    videoQuality: '1080p',
    storageLocation: 'local',
    emailNotifications: true,
    desktopNotifications: true,
    defaultModel: 'groq/llama-3.1-70b-versatile' // Default model
  })
  
  const [apiKeys, setApiKeys] = useState([])
  const [newApiKey, setNewApiKey] = useState({
    name: '',
    provider: 'openai',
    key: ''
  })
  const [testResult, setTestResult] = useState(null)
  const [testLoading, setTestLoading] = useState(false)
  const [availableModels, setAvailableModels] = useState([])
  const [modelsLoading, setModelsLoading] = useState(false)
  const [changingPassword, setChangingPassword] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [notice, setNotice] = useState(null)

  const passwordForm = useForm({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current: '', new: '', confirm: '' },
  })

  // Load API keys and models when component mounts
  useEffect(() => {
    loadApiKeys()
    loadAvailableModels()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id])

  const loadApiKeys = async () => {
    if (!user?.id) return
    try {
      const response = await api.request(`/api-keys/user/${user.id}`)
      setApiKeys(response.api_keys || [])
    } catch (error) {
      console.error('Failed to load API keys:', error)
    }
  }

  const loadAvailableModels = async () => {
    setModelsLoading(true)
    try {
      const response = await api.getAvailableModels()
      setAvailableModels(response.models || [])
      
      // Set default model if it exists in the available models
      const defaultModelResponse = await api.getDefaultModel()
      if (defaultModelResponse.default_model) {
        setSettings(prev => ({ ...prev, defaultModel: defaultModelResponse.default_model }))
      }
    } catch (error) {
      console.error('Failed to load available models:', error)
      // Fallback to predefined models
      const fallbackModels = [
        "gpt-4", "gpt-3.5-turbo",
        "claude-2", "claude-instant-1",
        "gemini-pro",
        "groq/llama-3.1-8b-instant",
        "groq/llama-3.1-70b-versatile",
        "groq/llama-3.1-405b-reasoning",
        "groq/mixtral-8x7b-32768",
        "groq/gemma-7b-it"
      ]
      setAvailableModels(fallbackModels)
    } finally {
      setModelsLoading(false)
    }
  }

  const handleSave = () => {
    // In a real app, this would save to a backend or local storage
    console.log('Saving settings:', settings)
    alert('Settings saved successfully!')
  }

  const handleChange = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }))
  }
  
  const handleAddApiKey = async () => {
    if (!newApiKey.name || !newApiKey.key) {
      alert('Please fill in all fields')
      return
    }
    
    try {
      const response = await api.request('/api-keys', {
        method: 'POST',
        body: {
          user_id: user?.id,
          name: newApiKey.name,
          provider: newApiKey.provider,
          key: newApiKey.key
        }
      })
      
      if (response.api_key) {
        setApiKeys(prev => [...prev, response.api_key])
        setNewApiKey({ name: '', provider: 'openai', key: '' })
        alert('API key added successfully!')
      }
    } catch (error) {
      console.error('Failed to add API key:', error)
      alert('Failed to add API key')
    }
  }
  
  const handleDeleteApiKey = async (apiKeyId) => {
    if (!window.confirm('Are you sure you want to delete this API key?')) {
      return
    }
    
    try {
      const response = await api.request(`/api-keys/${apiKeyId}`, {
        method: 'DELETE',
      })
      
      if (response.message) {
        setApiKeys(prev => prev.filter(key => key.id !== apiKeyId))
        alert('API key deleted successfully!')
      }
    } catch (error) {
      console.error('Failed to delete API key:', error)
      alert('Failed to delete API key')
    }
  }
  
  const handleTestApiKey = async () => {
    if (!newApiKey.provider || !newApiKey.key) {
      alert('Please select a provider and enter an API key')
      return
    }
    
    setTestLoading(true)
    setTestResult(null)
    
    try {
      const response = await api.request('/api-keys/test', {
        method: 'POST',
        body: {
          provider: newApiKey.provider,
          key: newApiKey.key
        }
      })
      
      setTestResult(response)
    } catch (error) {
      console.error('Failed to test API key:', error)
      setTestResult({ success: false, error: error.message || 'Failed to test API key' })
    } finally {
      setTestLoading(false)
    }
  }

  const handleChangePassword = async (values) => {
    setChangingPassword(true)
    setNotice(null)
    try {
      await api.updateMe({ password: values.new })
      setNotice('Password changed successfully')
      passwordForm.reset()
    } catch (error) {
      console.error('Failed to change password:', error)
      alert(error.message || 'Failed to change password')
    } finally {
      setChangingPassword(false)
    }
  }

  const handleDeleteAccount = async () => {
    if (!window.confirm('Permanently delete your account and all its data? This cannot be undone.')) {
      return
    }
    setDeleting(true)
    try {
      await api.deleteMe()
      await api.logout()
    } catch (error) {
      console.error('Failed to delete account:', error)
    } finally {
      useAuthStore.getState().logout()
      setDeleting(false)
      navigate('/login')
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-white">Settings</h1>
            <Button onClick={handleSave} className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600">
              <Save className="h-4 w-4 mr-2" />
              Save Changes
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Sidebar Navigation */}
          <div className="lg:col-span-1">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white">Settings</CardTitle>
                <CardDescription className="text-slate-400">
                  Manage your account preferences and application settings
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <Button variant="ghost" className="w-full justify-start text-white hover:bg-slate-700">
                  <Palette className="h-4 w-4 mr-2" />
                  Appearance
                </Button>
                <Button variant="ghost" className="w-full justify-start text-white hover:bg-slate-700">
                  <Bell className="h-4 w-4 mr-2" />
                  Notifications
                </Button>
                <Button variant="ghost" className="w-full justify-start text-white hover:bg-slate-700">
                  <Shield className="h-4 w-4 mr-2" />
                  Privacy & Security
                </Button>
                <Button variant="ghost" className="w-full justify-start text-white hover:bg-slate-700">
                  <Database className="h-4 w-4 mr-2" />
                  Data & Storage
                </Button>
                <Button variant="ghost" className="w-full justify-start text-white hover:bg-slate-700">
                  <Cpu className="h-4 w-4 mr-2" />
                  AI Models
                </Button>
                <Button variant="ghost" className="w-full justify-start text-white hover:bg-slate-700">
                  <Cloud className="h-4 w-4 mr-2" />
                  Integrations
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Settings Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Appearance Settings */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center">
                  <Palette className="h-5 w-5 mr-2" />
                  Appearance
                </CardTitle>
                <CardDescription className="text-slate-400">
                  Customize the look and feel of the application
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-white">Theme</Label>
                    <p className="text-sm text-slate-400">Select your preferred color scheme</p>
                  </div>
                  <Select value={settings.theme} onValueChange={(value) => handleChange('theme', value)}>
                    <SelectTrigger className="w-40 bg-slate-700 border-slate-600 text-white">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="light">Light</SelectItem>
                      <SelectItem value="dark">Dark</SelectItem>
                      <SelectItem value="system">System</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>

            {/* Notifications Settings */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center">
                  <Bell className="h-5 w-5 mr-2" />
                  Notifications
                </CardTitle>
                <CardDescription className="text-slate-400">
                  Configure how you receive notifications
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-white">Email Notifications</Label>
                    <p className="text-sm text-slate-400">Receive notifications via email</p>
                  </div>
                  <Switch
                    checked={settings.emailNotifications}
                    onCheckedChange={(checked) => handleChange('emailNotifications', checked)}
                  />
                </div>
                <Separator className="bg-slate-700" />
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-white">Desktop Notifications</Label>
                    <p className="text-sm text-slate-400">Show notifications on your desktop</p>
                  </div>
                  <Switch
                    checked={settings.desktopNotifications}
                    onCheckedChange={(checked) => handleChange('desktopNotifications', checked)}
                  />
                </div>
              </CardContent>
            </Card>

            {/* Data & Storage Settings */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center">
                  <Database className="h-5 w-5 mr-2" />
                  Data & Storage
                </CardTitle>
                <CardDescription className="text-slate-400">
                  Manage your data storage preferences
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-white">Auto-save Projects</Label>
                    <p className="text-sm text-slate-400">Automatically save your projects</p>
                  </div>
                  <Switch
                    checked={settings.autoSave}
                    onCheckedChange={(checked) => handleChange('autoSave', checked)}
                  />
                </div>
                <Separator className="bg-slate-700" />
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-white">Default Video Quality</Label>
                    <p className="text-sm text-slate-400">Select the default output quality</p>
                  </div>
                  <Select value={settings.videoQuality} onValueChange={(value) => handleChange('videoQuality', value)}>
                    <SelectTrigger className="w-32 bg-slate-700 border-slate-600 text-white">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="720p">720p</SelectItem>
                      <SelectItem value="1080p">1080p</SelectItem>
                      <SelectItem value="4k">4K</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Separator className="bg-slate-700" />
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-white">Storage Location</Label>
                    <p className="text-sm text-slate-400">Where to store your generated videos</p>
                  </div>
                  <Select value={settings.storageLocation} onValueChange={(value) => handleChange('storageLocation', value)}>
                    <SelectTrigger className="w-32 bg-slate-700 border-slate-600 text-white">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="local">Local</SelectItem>
                      <SelectItem value="cloud">Cloud</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>

            {/* AI Model Settings */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center">
                  <Cpu className="h-5 w-5 mr-2" />
                  AI Model Settings
                </CardTitle>
                <CardDescription className="text-slate-400">
                  Configure default AI models for content generation
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-white">Default AI Model</Label>
                    <p className="text-sm text-slate-400">Select the default model for script generation</p>
                  </div>
                  <div className="w-64">
                    {modelsLoading ? (
                      <div className="flex items-center justify-center p-2">
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-purple-500 mr-2"></div>
                        <span className="text-slate-400 text-sm">Loading models...</span>
                      </div>
                    ) : (
                      <Select 
                        value={settings.defaultModel} 
                        onValueChange={(value) => handleChange('defaultModel', value)}
                      >
                        <SelectTrigger className="bg-slate-700 border-slate-600 text-white">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {availableModels.map((model) => (
                            <SelectItem key={model} value={model}>
                              {model}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </div>
                </div>
                <div className="text-sm text-slate-400">
                  <p>The selected model will be used by default for all AI-powered content generation tasks.</p>
                  <p className="mt-1">Models are fetched dynamically from your LiteLLM proxy configuration.</p>
                </div>
              </CardContent>
            </Card>

            {/* Security Settings */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center">
                  <Key className="h-5 w-5 mr-2" />
                  Security
                </CardTitle>
                <CardDescription className="text-slate-400">
                  Change your password or delete your account
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {notice && (
                  <div className="p-3 rounded-md bg-green-900/50 border border-green-800 text-green-300">
                    {notice}
                  </div>
                )}
                <div>
                  <Label className="text-white">Current Password</Label>
                  <Input
                    type="password"
                    {...passwordForm.register('current')}
                    className="mt-2 bg-slate-700 border-slate-600 text-white"
                  />
                  {passwordForm.formState.errors.current && (
                    <p className="text-red-400 text-sm mt-1">
                      {passwordForm.formState.errors.current.message}
                    </p>
                  )}
                </div>
                <div>
                  <Label className="text-white">New Password</Label>
                  <Input
                    type="password"
                    {...passwordForm.register('new')}
                    className="mt-2 bg-slate-700 border-slate-600 text-white"
                  />
                  {passwordForm.formState.errors.new && (
                    <p className="text-red-400 text-sm mt-1">
                      {passwordForm.formState.errors.new.message}
                    </p>
                  )}
                </div>
                <div>
                  <Label className="text-white">Confirm New Password</Label>
                  <Input
                    type="password"
                    {...passwordForm.register('confirm')}
                    className="mt-2 bg-slate-700 border-slate-600 text-white"
                  />
                  {passwordForm.formState.errors.confirm && (
                    <p className="text-red-400 text-sm mt-1">
                      {passwordForm.formState.errors.confirm.message}
                    </p>
                  )}
                </div>
                <Button
                  onClick={passwordForm.handleSubmit(handleChangePassword)}
                  disabled={changingPassword}
                  className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
                >
                  {changingPassword ? 'Updating...' : 'Update Password'}
                </Button>
                <Separator className="bg-slate-700" />
                <div className="flex justify-between items-center">
                  <div>
                    <h3 className="text-red-400 font-medium">Delete Account</h3>
                    <p className="text-slate-400 text-sm">Permanently delete your account and all data</p>
                  </div>
                  <Button variant="destructive" onClick={handleDeleteAccount} disabled={deleting}>
                    <Trash2 className="h-4 w-4 mr-2" />
                    {deleting ? 'Deleting...' : 'Delete Account'}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* API Settings */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center">
                  <Cloud className="h-5 w-5 mr-2" />
                  API Integration
                </CardTitle>
                <CardDescription className="text-slate-400">
                  Configure and manage your LLM API keys
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  <div>
                    <Label className="text-white">Add New API Key</Label>
                    <p className="text-sm text-slate-400 mb-2">Add and manage your LLM API keys</p>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label className="text-white text-sm mb-1">Name</Label>
                      <Input
                        value={newApiKey.name}
                        onChange={(e) => setNewApiKey(prev => ({ ...prev, name: e.target.value }))}
                        className="bg-slate-700 border-slate-600 text-white"
                        placeholder="e.g., OpenAI Production"
                      />
                    </div>
                    <div>
                      <Label className="text-white text-sm mb-1">Provider</Label>
                      <Select value={newApiKey.provider} onValueChange={(value) => setNewApiKey(prev => ({ ...prev, provider: value }))}>
                        <SelectTrigger className="bg-slate-700 border-slate-600 text-white">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="openai">OpenAI</SelectItem>
                          <SelectItem value="anthropic">Anthropic</SelectItem>
                          <SelectItem value="google">Google</SelectItem>
                          <SelectItem value="groq">Groq</SelectItem>
                          <SelectItem value="openrouter">OpenRouter</SelectItem>
                          <SelectItem value="replicate">Replicate</SelectItem>
                          <SelectItem value="togetherai">TogetherAI</SelectItem>
                          <SelectItem value="azure">Azure OpenAI</SelectItem>
                          <SelectItem value="vertex">Vertex AI</SelectItem>
                          <SelectItem value="huggingface">Hugging Face</SelectItem>
                          <SelectItem value="bedrock">Amazon Bedrock</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  
                  <div>
                    <Label className="text-white text-sm mb-1">API Key</Label>
                    <Input
                      type="password"
                      value={newApiKey.key}
                      onChange={(e) => setNewApiKey(prev => ({ ...prev, key: e.target.value }))}
                      className="bg-slate-700 border-slate-600 text-white"
                      placeholder="Enter your API key"
                    />
                  </div>
                  
                  <div className="flex flex-wrap gap-2">
                    <Button 
                      onClick={handleAddApiKey}
                      className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
                    >
                      <Plus className="h-4 w-4 mr-2" />
                      Add API Key
                    </Button>
                    <Button 
                      onClick={handleTestApiKey}
                      disabled={testLoading}
                      variant="outline"
                      className="border-slate-600 text-slate-300 hover:bg-slate-700"
                    >
                      {testLoading ? (
                        <>
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-purple-500 mr-2"></div>
                          Testing...
                        </>
                      ) : (
                        'Test API Key'
                      )}
                    </Button>
                  </div>
                  
                  {testResult && (
                    <div className={`p-3 rounded-md ${testResult.success ? 'bg-green-900/50 border border-green-800' : 'bg-red-900/50 border border-red-800'}`}>
                      <div className="flex items-center">
                        {testResult.success ? (
                          <Check className="h-4 w-4 text-green-400 mr-2" />
                        ) : (
                          <X className="h-4 w-4 text-red-400 mr-2" />
                        )}
                        <span className={testResult.success ? 'text-green-300' : 'text-red-300'}>
                          {testResult.success ? 'API key is valid' : 'API key test failed'}
                        </span>
                      </div>
                      {testResult.response && (
                        <p className="text-sm text-slate-300 mt-1">Response: {testResult.response}</p>
                      )}
                      {testResult.error && (
                        <p className="text-sm text-slate-300 mt-1">Error: {testResult.error}</p>
                      )}
                    </div>
                  )}
                </div>
                
                <Separator className="bg-slate-700" />
                
                <div>
                  <Label className="text-white">Saved API Keys</Label>
                  <p className="text-sm text-slate-400 mb-2">Manage your existing API keys</p>
                  
                  {apiKeys.length === 0 ? (
                    <p className="text-slate-400 text-sm">No API keys saved yet</p>
                  ) : (
                    <div className="space-y-2">
                      {apiKeys.map((apiKey) => (
                        <div key={apiKey.id} className="flex items-center justify-between p-3 bg-slate-700/50 rounded-md">
                          <div>
                            <div className="font-medium text-white">{apiKey.name}</div>
                            <div className="text-sm text-slate-400 capitalize">{apiKey.provider}</div>
                          </div>
                          <Button 
                            onClick={() => handleDeleteApiKey(apiKey.id)}
                            variant="outline" 
                            size="sm"
                            className="border-red-600 text-red-400 hover:bg-red-900/50"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  )
}

export default SettingsPage