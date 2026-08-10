import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Separator } from '@/components/ui/separator'
import { Save, Upload, Key, CreditCard, User } from 'lucide-react'

const ProfilePage = () => {
  const [profile, setProfile] = useState({
    name: 'John Doe',
    email: 'john@example.com',
    username: 'johndoe',
    bio: 'AI video creator and content producer',
    avatar: '',
  })

  const [password, setPassword] = useState({
    current: '',
    new: '',
    confirm: '',
  })

  const [billing, setBilling] = useState({
    plan: 'Pro',
    nextBilling: '2025-10-01',
    paymentMethod: 'Visa ending in 1234',
  })

  const handleSaveProfile = () => {
    // In a real app, this would save to a backend
    console.log('Saving profile:', profile)
    alert('Profile updated successfully!')
  }

  const handleChangePassword = () => {
    // In a real app, this would save to a backend
    if (password.new !== password.confirm) {
      alert('New passwords do not match!')
      return
    }
    console.log('Changing password')
    alert('Password changed successfully!')
    setPassword({ current: '', new: '', confirm: '' })
  }

  const handleProfileChange = (key, value) => {
    setProfile(prev => ({ ...prev, [key]: value }))
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-white">Profile</h1>
            <Button onClick={handleSaveProfile} className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600">
              <Save className="h-4 w-4 mr-2" />
              Save Changes
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
                    <AvatarImage src={profile.avatar} alt={profile.name} />
                    <AvatarFallback className="bg-gradient-to-r from-purple-500 to-pink-500 text-white text-2xl">
                      {profile.name.charAt(0)}
                    </AvatarFallback>
                  </Avatar>
                  <Button variant="outline" className="border-slate-600 text-slate-300 hover:bg-slate-700">
                    <Upload className="h-4 w-4 mr-2" />
                    Upload New Photo
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="text-center">
                <h2 className="text-xl font-bold text-white">{profile.name}</h2>
                <p className="text-slate-400">@{profile.username}</p>
                <p className="text-sm text-slate-400 mt-2">{profile.bio}</p>
              </CardContent>
            </Card>

            {/* Billing Info */}
            <Card className="bg-slate-800/50 border-slate-700 mt-6">
              <CardHeader>
                <CardTitle className="text-white flex items-center">
                  <CreditCard className="h-5 w-5 mr-2" />
                  Subscription
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label className="text-slate-400">Current Plan</Label>
                  <p className="text-white font-medium">{billing.plan}</p>
                </div>
                <div>
                  <Label className="text-slate-400">Next Billing Date</Label>
                  <p className="text-white">{billing.nextBilling}</p>
                </div>
                <div>
                  <Label className="text-slate-400">Payment Method</Label>
                  <p className="text-white">{billing.paymentMethod}</p>
                </div>
                <Button className="w-full mt-4 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600">
                  Manage Subscription
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Profile Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Profile Information */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center">
                  <User className="h-5 w-5 mr-2" />
                  Profile Information
                </CardTitle>
                <CardDescription className="text-slate-400">
                  Update your personal information and bio
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <Label className="text-white">Full Name</Label>
                    <Input
                      value={profile.name}
                      onChange={(e) => handleProfileChange('name', e.target.value)}
                      className="mt-2 bg-slate-700 border-slate-600 text-white"
                    />
                  </div>
                  <div>
                    <Label className="text-white">Username</Label>
                    <Input
                      value={profile.username}
                      onChange={(e) => handleProfileChange('username', e.target.value)}
                      className="mt-2 bg-slate-700 border-slate-600 text-white"
                    />
                  </div>
                </div>
                <div>
                  <Label className="text-white">Email</Label>
                  <Input
                    type="email"
                    value={profile.email}
                    onChange={(e) => handleProfileChange('email', e.target.value)}
                    className="mt-2 bg-slate-700 border-slate-600 text-white"
                  />
                </div>
                <div>
                  <Label className="text-white">Bio</Label>
                  <Textarea
                    value={profile.bio}
                    onChange={(e) => handleProfileChange('bio', e.target.value)}
                    className="mt-2 bg-slate-700 border-slate-600 text-white"
                    rows={4}
                  />
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
                    value={password.current}
                    onChange={(e) => setPassword(prev => ({ ...prev, current: e.target.value }))}
                    className="mt-2 bg-slate-700 border-slate-600 text-white"
                  />
                </div>
                <div>
                  <Label className="text-white">New Password</Label>
                  <Input
                    type="password"
                    value={password.new}
                    onChange={(e) => setPassword(prev => ({ ...prev, new: e.target.value }))}
                    className="mt-2 bg-slate-700 border-slate-600 text-white"
                  />
                </div>
                <div>
                  <Label className="text-white">Confirm New Password</Label>
                  <Input
                    type="password"
                    value={password.confirm}
                    onChange={(e) => setPassword(prev => ({ ...prev, confirm: e.target.value }))}
                    className="mt-2 bg-slate-700 border-slate-600 text-white"
                  />
                </div>
                <Button onClick={handleChangePassword} className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600">
                  Update Password
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
                <div className="flex justify-between items-center">
                  <div>
                    <h3 className="text-white font-medium">Two-Factor Authentication</h3>
                    <p className="text-slate-400 text-sm">Add an extra layer of security to your account</p>
                  </div>
                  <Button variant="outline" className="border-slate-600 text-slate-300 hover:bg-slate-700">
                    Enable
                  </Button>
                </div>
                <Separator className="bg-slate-700" />
                <div className="flex justify-between items-center">
                  <div>
                    <h3 className="text-white font-medium">Download Your Data</h3>
                    <p className="text-slate-400 text-sm">Get a copy of your personal data</p>
                  </div>
                  <Button variant="outline" className="border-slate-600 text-slate-300 hover:bg-slate-700">
                    Download
                  </Button>
                </div>
                <Separator className="bg-slate-700" />
                <div className="flex justify-between items-center">
                  <div>
                    <h3 className="text-red-400 font-medium">Delete Account</h3>
                    <p className="text-slate-400 text-sm">Permanently delete your account and all data</p>
                  </div>
                  <Button variant="destructive">Delete Account</Button>
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