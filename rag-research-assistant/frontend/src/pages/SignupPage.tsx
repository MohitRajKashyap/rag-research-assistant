import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Mail, Lock, User, Zap } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { Button, Input } from '@/components/ui'
import toast from 'react-hot-toast'

export default function SignupPage() {
  const navigate = useNavigate()
  const { signup, isLoading } = useAuthStore()
  const [form, setForm] = useState({ email: '', username: '', password: '', full_name: '' })
  const [errors, setErrors] = useState<Record<string, string>>({})

  const validate = () => {
    const errs: Record<string, string> = {}
    if (!form.email) errs.email = 'Email is required'
    if (!form.username || form.username.length < 3) errs.username = 'Username must be 3+ characters'
    if (!/^[a-zA-Z0-9_-]+$/.test(form.username)) errs.username = 'Only letters, numbers, _ and - allowed'
    if (!form.password || form.password.length < 8) errs.password = 'Password must be 8+ characters'
    if (!/[A-Z]/.test(form.password)) errs.password = 'Password needs an uppercase letter'
    if (!/[0-9]/.test(form.password)) errs.password = 'Password needs a number'
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    try {
      await signup(form)
      toast.success('Account created! Welcome!')
      navigate('/chat')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || 'Signup failed')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-indigo-100 dark:from-gray-950 dark:to-gray-900 p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-primary-600 rounded-xl mb-3 shadow-lg">
            <Zap size={24} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">RAG Research Assistant</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Create your research workspace</p>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">Create account</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Full name"
              placeholder="Jane Smith"
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              icon={<User size={16} />}
            />
            <Input
              label="Email *"
              type="email"
              placeholder="you@example.com"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              error={errors.email}
              icon={<Mail size={16} />}
            />
            <Input
              label="Username *"
              placeholder="researcher42"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              error={errors.username}
              icon={<User size={16} />}
            />
            <Input
              label="Password *"
              type="password"
              placeholder="Min 8 chars, 1 uppercase, 1 number"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              error={errors.password}
              icon={<Lock size={16} />}
            />
            <Button type="submit" loading={isLoading} className="w-full" size="lg">
              Create account
            </Button>
          </form>

          <p className="text-center text-sm text-gray-500 dark:text-gray-400 mt-5">
            Already have an account?{' '}
            <Link to="/login" className="text-primary-600 hover:underline font-medium">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
