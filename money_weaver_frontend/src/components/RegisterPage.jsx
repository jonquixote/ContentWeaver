import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Play, Eye, EyeOff, Github, Chrome } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

const RegisterPage = () => {
  const [credentials, setCredentials] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
  })
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const { register } = useAuth()

  const handleRegister = async (e) => {
    e.preventDefault()
    setIsLoading(true)
    setError('')

    // Basic validation
    if (credentials.password !== credentials.confirmPassword) {
      setError('Passwords do not match')
      setIsLoading(false)
      return
    }

    if (credentials.password.length < 8) {
      setError('Password must be at least 8 characters long')
      setIsLoading(false)
      return
    }

    try {
      await register({
        name: credentials.name,
        email: credentials.email,
        password: credentials.password
      })
      navigate('/dashboard')
    } catch (err) {
      setError(err.message || 'Failed to create account. Please try again.')
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
            <CardTitle className="text-2xl text-white text-center">Create an Account</CardTitle>
            <CardDescription className="text-center text-slate-400">
              Sign up to get started with our platform
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleRegister} className="space-y-4">
              {error && (
                <div className="bg-red-900/50 border border-red-800 text-red-300 p-3 rounded-md text-sm">
                  {error}
                </div>
              )}
              
              <div className="space-y-2">
                <Label htmlFor="name" className="text-white">Full Name</Label>
                <Input
                  id="name"
                  name="name"
                  type="text"
                  value={credentials.name}
                  onChange={handleChange}
                  required
                  className="bg-slate-700 border-slate-600 text-white placeholder:text-slate-400"
                  placeholder="Enter your full name"
                />
              </div>
              
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
                    placeholder="Create a password"
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
                <p className="text-xs text-slate-400">Must be at least 8 characters</p>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="confirmPassword" className="text-white">Confirm Password</Label>
                <div className="relative">
                  <Input
                    id="confirmPassword"
                    name="confirmPassword"
                    type={showConfirmPassword ? "text" : "password"}
                    value={credentials.confirmPassword}
                    onChange={handleChange}
                    required
                    className="bg-slate-700 border-slate-600 text-white placeholder:text-slate-400 pr-10"
                    placeholder="Confirm your password"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  >
                    {showConfirmPassword ? (
                      <EyeOff className="h-4 w-4 text-slate-400" />
                    ) : (
                      <Eye className="h-4 w-4 text-slate-400" />
                    )}
                  </Button>
                </div>
              </div>
              
              <Button 
                type="submit" 
                disabled={isLoading}
                className="w-full bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
              >
                {isLoading ? (
                  <div className="flex items-center">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Creating account...
                  </div>
                ) : (
                  'Create Account'
                )}
              </Button>
            </form>
            
            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <Separator className="w-full bg-slate-700" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-slate-800 px-2 text-slate-400">Or sign up with</span>
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
              Already have an account?{' '}
              <Button 
                variant="link" 
                className="text-purple-400 hover:text-purple-300 p-0"
                onClick={() => navigate('/login')}
              >
                Sign in
              </Button>
            </p>
          </CardFooter>
        </Card>
        
        <div className="mt-8 text-center">
          <p className="text-xs text-slate-500">
            By signing up, you agree to our{' '}
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

export default RegisterPage