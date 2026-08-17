import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Play, Eye, EyeOff, Github, Chrome } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

const LoginPage = () => {
  const [credentials, setCredentials] = useState({
    email: '',
    password: '',
  })
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const { login } = useAuth()

  const handleLogin = async (e) => {
    e.preventDefault()
    setIsLoading(true)
    setError('')

    try {
      await login(credentials)
      navigate('/dashboard')
    } catch (err) {
      setError(err.message || 'Invalid email or password. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleSocialLogin = () => {
    // In a real app, this would initiate OAuth flow
    navigate('/dashboard')
  }

  const handleChange = (e) => {
    const { name, value } = e.target
    setCredentials(prev => ({ ...prev, [name]: value }))
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <div className="h-12 w-12 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 flex items-center justify-center">
              <Play className="h-6 w-6 text-white" />
            </div>
            <h1 className="text-3xl font-bold text-white ml-3">MoneyWeaver</h1>
          </div>
          <p className="text-slate-400">AI-Powered Video Generation Platform</p>
        </div>

        <Card className="bg-slate-800/50 border-slate-700">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl text-white text-center">Welcome Back</CardTitle>
            <CardDescription className="text-center text-slate-400">
              Sign in to your account to continue
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleLogin} className="space-y-4">
              {error && (
                <div className="bg-red-900/50 border border-red-800 text-red-300 p-3 rounded-md text-sm">
                  {error}
                </div>
              )}
              
              <div className="space-y-2">
                <Label htmlFor="email" className="text-white">Email</Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  value={credentials.email}
                  onChange={handleChange}
                  required
                  className="bg-slate-700 border-slate-600 text-white placeholder:text-slate-400"
                  placeholder="Enter your email"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="password" className="text-white">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    value={credentials.password}
                    onChange={handleChange}
                    required
                    className="bg-slate-700 border-slate-600 text-white placeholder:text-slate-400 pr-10"
                    placeholder="Enter your password"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4 text-slate-400" />
                    ) : (
                      <Eye className="h-4 w-4 text-slate-400" />
                    )}
                  </Button>
                </div>
              </div>
              
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <input
                    id="remember"
                    type="checkbox"
                    className="h-4 w-4 rounded border-slate-600 bg-slate-700 text-purple-500 focus:ring-purple-500"
                  />
                  <label htmlFor="remember" className="ml-2 block text-sm text-slate-300">
                    Remember me
                  </label>
                </div>
                <Button type="button" variant="link" className="text-sm text-purple-400 hover:text-purple-300 p-0">
                  Forgot password?
                </Button>
              </div>
              
              <Button 
                type="submit" 
                disabled={isLoading}
                className="w-full bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
              >
                {isLoading ? (
                  <div className="flex items-center">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Signing in...
                  </div>
                ) : (
                  'Sign In'
                )}
              </Button>
            </form>
            
            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <Separator className="w-full bg-slate-700" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-slate-800 px-2 text-slate-400">Or continue with</span>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <Button
                variant="outline"
                onClick={() => handleSocialLogin('google')}
                className="border-slate-600 text-slate-300 hover:bg-slate-700"
              >
                <Chrome className="h-4 w-4 mr-2" />
                Google
              </Button>
              <Button
                variant="outline"
                onClick={() => handleSocialLogin('github')}
                className="border-slate-600 text-slate-300 hover:bg-slate-700"
              >
                <Github className="h-4 w-4 mr-2" />
                GitHub
              </Button>
            </div>
          </CardContent>
          <CardFooter className="flex flex-col">
            <p className="text-sm text-slate-400">
              Don't have an account?{' '}
              <Button 
                variant="link" 
                className="text-purple-400 hover:text-purple-300 p-0"
                onClick={() => navigate('/register')}
              >
                Sign up
              </Button>
            </p>
          </CardFooter>
        </Card>
        
        <div className="mt-8 text-center">
          <p className="text-xs text-slate-500">
            By signing in, you agree to our{' '}
            <Button variant="link" className="text-purple-400 hover:text-purple-300 p-0 text-xs">
              Terms of Service
            </Button>{' '}
            and{' '}
            <Button variant="link" className="text-purple-400 hover:text-purple-300 p-0 text-xs">
              Privacy Policy
            </Button>
          </p>
        </div>
      </div>
    </div>
  )
}

export default LoginPage