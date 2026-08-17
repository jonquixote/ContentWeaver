import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Save, Key, User, Trash2 } from 'lucide-react'
import api from '@/services/api'
import { useAuthStore } from '@/store/authStore'
import { useMe } from '@/hooks/useUser'

const profileSchema = z.object({
  username: z.string().min(3, 'Username must be at least 3 characters'),
  email: z.string().email('Invalid email address'),
})

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

const ProfilePage = () => {
  const navigate = useNavigate()
  const storeUser = useAuthStore((s) => s.user)
  const [savingProfile, setSavingProfile] = useState(false)
  const [changingPassword, setChangingPassword] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const profileForm = useForm({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      username: storeUser?.username || '',
      email: storeUser?.email || '',
    },
  })

  const passwordForm = useForm({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current: '', new: '', confirm: '' },
  })

  const { data: meData, error: meError } = useMe()

  useEffect(() => {
    // Refresh the logged-in user's profile from the backend.
    if (meData) {
      useAuthStore.getState().setUser(meData)
      profileForm.reset({ username: meData.username, email: meData.email })
    }
  }, [meData, profileForm])

  useEffect(() => {
    if (meError) {
      console.error('Failed to load profile:', meError)
      setError(meError.message || 'Failed to load profile')
    }
  }, [meError])

  const handleSaveProfile = async (values) => {
    setSavingProfile(true)
    setError(null)
    setNotice(null)
    try {
      const updated = await api.updateMe({
        username: values.username,
        email: values.email,
      })
      useAuthStore.getState().setUser(updated)
      setNotice('Profile updated successfully')
    } catch (err) {
      setError(err.message || 'Failed to update profile')
    } finally {
      setSavingProfile(false)
    }
  }

  const handleChangePassword = async (values) => {
    setChangingPassword(true)
    setError(null)
    setNotice(null)
    try {
      await api.updateMe({ password: values.new })
      setNotice('Password changed successfully')
      passwordForm.reset()
    } catch (err) {
      setError(err.message || 'Failed to change password')
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
    } catch (err) {
      console.error('Failed to delete account:', err)
    } finally {
      useAuthStore.getState().logout()
      setDeleting(false)
      navigate('/login')
    }
  }

  const user = storeUser || {}
  const initials = (user.username || 'U').slice(0, 2).toUpperCase()

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-white">Profile</h1>
            <Button
              onClick={profileForm.handleSubmit(handleSaveProfile)}
              disabled={savingProfile}
              className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
            >
              <Save className="h-4 w-4 mr-2" />
              {savingProfile ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Profile Sidebar */}
          <div className="lg:col-span-1">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <div className="flex flex-col items-center space-y-4">
                  <Avatar className="h-24 w-24">
                    <AvatarImage src={user.avatar || ''} alt={user.username || 'User'} />
                    <AvatarFallback className="bg-gradient-to-r from-purple-500 to-pink-500 text-white text-2xl">
                      {initials}
                    </AvatarFallback>
                  </Avatar>
                </div>
              </CardHeader>
              <CardContent className="text-center">
                <h2 className="text-xl font-bold text-white">{user.username || 'User'}</h2>
                <p className="text-slate-400">@{user.username}</p>
                <p className="text-sm text-slate-400 mt-2">{user.email}</p>
              </CardContent>
            </Card>
          </div>

          {/* Profile Content */}
          <div className="lg:col-span-2 space-y-6">
            {error && (
              <div className="p-3 rounded-md bg-red-900/50 border border-red-800 text-red-300">
                {error}
              </div>
            )}
            {notice && (
              <div className="p-3 rounded-md bg-green-900/50 border border-green-800 text-green-300">
                {notice}
              </div>
            )}

            {/* Profile Information */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center">
                  <User className="h-5 w-5 mr-2" />
                  Profile Information
                </CardTitle>
                <CardDescription className="text-slate-400">
                  Update your username and email
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <Label className="text-white">Username</Label>
                    <Input
                      {...profileForm.register('username')}
                      className="mt-2 bg-slate-700 border-slate-600 text-white"
                    />
                    {profileForm.formState.errors.username && (
                      <p className="text-red-400 text-sm mt-1">
                        {profileForm.formState.errors.username.message}
                      </p>
                    )}
                  </div>
                  <div>
                    <Label className="text-white">Email</Label>
                    <Input
                      type="email"
                      {...profileForm.register('email')}
                      className="mt-2 bg-slate-700 border-slate-600 text-white"
                    />
                    {profileForm.formState.errors.email && (
                      <p className="text-red-400 text-sm mt-1">
                        {profileForm.formState.errors.email.message}
                      </p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Password Settings */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center">
                  <Key className="h-5 w-5 mr-2" />
                  Change Password
                </CardTitle>
                <CardDescription className="text-slate-400">
                  Update your password to keep your account secure
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
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
              </CardContent>
            </Card>

            {/* Account Actions */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white">Account Actions</CardTitle>
                <CardDescription className="text-slate-400">
                  Manage your account settings and preferences
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
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
          </div>
        </div>
      </main>
    </div>
  )
}

export default ProfilePage