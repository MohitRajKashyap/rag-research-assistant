// ============================================================
// Search Page
// ============================================================
import { useState } from 'react'
import { Search, FileText, Clock } from 'lucide-react'
import { useSearchDocuments } from '@/hooks/useApi'
import { Button, Input, Card, Spinner, EmptyState, Badge } from '@/components/ui'
import { SearchResult } from '@/types'

export function SearchPage() {
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(5)
  const searchMutation = useSearchDocuments()

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    await searchMutation.mutateAsync({ query, top_k: topK })
  }

  const results: SearchResult[] = searchMutation.data?.results || []

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Semantic Search</h1>
          <p className="text-sm text-gray-500 mt-0.5">Find relevant passages across all your research documents</p>
        </div>

        <form onSubmit={handleSearch} className="flex gap-3">
          <div className="flex-1">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search your research documents..."
              icon={<Search size={16} />}
            />
          </div>
          <select
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-sm text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            {[3, 5, 10].map((k) => <option key={k} value={k}>Top {k}</option>)}
          </select>
          <Button type="submit" loading={searchMutation.isPending} icon={<Search size={14} />}>
            Search
          </Button>
        </form>

        {searchMutation.isPending && <div className="flex justify-center py-12"><Spinner size={32} /></div>}

        {searchMutation.data && (
          <div>
            <p className="text-sm text-gray-500 mb-3">
              {results.length} result{results.length !== 1 ? 's' : ''} ·{' '}
              {searchMutation.data.search_latency_ms}ms
            </p>
            {results.length === 0 ? (
              <EmptyState icon={<Search size={40} />} title="No results found" description="Try different keywords or upload more documents." />
            ) : (
              <div className="space-y-3">
                {results.map((r, i) => (
                  <Card key={i} className="p-4">
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div className="flex items-center gap-2">
                        <FileText size={14} className="text-primary-500 flex-shrink-0" />
                        <span className="text-sm font-semibold text-gray-900 dark:text-white truncate">{r.document_title}</span>
                      </div>
                      <Badge variant="success" className="flex-shrink-0">{(r.similarity_score * 100).toFixed(0)}% match</Badge>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-3">{r.chunk_content}</p>
                    {r.page_number && (
                      <p className="text-xs text-gray-400 mt-2">Page {r.page_number}</p>
                    )}
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ============================================================
// Collections Page
// ============================================================
import { useCollections, useCreateCollection, useDeleteCollection } from '@/hooks/useApi'
import { Plus, Trash2, FolderOpen } from 'lucide-react'
import { Modal } from '@/components/ui'

export function CollectionsPage() {
  const { data: collections = [], isLoading } = useCollections()
  const createColl = useCreateCollection()
  const deleteColl = useDeleteCollection()
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', color: '#6366f1' })

  const handleCreate = async () => {
    if (!form.name.trim()) return
    await createColl.mutateAsync(form)
    setShowCreate(false)
    setForm({ name: '', description: '', color: '#6366f1' })
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Collections</h1>
            <p className="text-sm text-gray-500 mt-0.5">Organise your documents into topic-based collections</p>
          </div>
          <Button onClick={() => setShowCreate(true)} icon={<Plus size={14} />}>New Collection</Button>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-20"><Spinner /></div>
        ) : collections.length === 0 ? (
          <EmptyState icon={<FolderOpen size={48} />} title="No collections yet" description="Create a collection to group related research documents." action={<Button onClick={() => setShowCreate(true)}>Create collection</Button>} />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {collections.map((c: { id: string; name: string; description?: string; color: string; document_count: number }) => (
              <Card key={c.id} className="p-5 group relative hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between">
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center mb-3" style={{ backgroundColor: c.color + '20', color: c.color }}>
                    <FolderOpen size={20} />
                  </div>
                  <button
                    onClick={() => deleteColl.mutate(c.id)}
                    className="opacity-0 group-hover:opacity-100 p-1.5 rounded text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-all"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
                <h3 className="font-semibold text-gray-900 dark:text-white">{c.name}</h3>
                {c.description && <p className="text-sm text-gray-500 mt-0.5 line-clamp-2">{c.description}</p>}
                <p className="text-xs text-gray-400 mt-2">{c.document_count} documents</p>
              </Card>
            ))}
          </div>
        )}

        <Modal open={showCreate} onClose={() => setShowCreate(false)} title="New Collection">
          <div className="space-y-4">
            <Input label="Name" placeholder="e.g. Machine Learning Papers" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <Input label="Description" placeholder="Optional description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Colour</label>
              <div className="flex gap-2">
                {['#6366f1','#8b5cf6','#ec4899','#ef4444','#f97316','#22c55e','#3b82f6'].map((color) => (
                  <button key={color} onClick={() => setForm({ ...form, color })} className="w-7 h-7 rounded-full transition-transform hover:scale-110" style={{ backgroundColor: color, outline: form.color === color ? `3px solid ${color}` : 'none', outlineOffset: '2px' }} />
                ))}
              </div>
            </div>
            <div className="flex gap-3 justify-end">
              <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button loading={createColl.isPending} onClick={handleCreate}>Create</Button>
            </div>
          </div>
        </Modal>
      </div>
    </div>
  )
}

// ============================================================
// Dashboard Page
// ============================================================
import { useSystemMetrics } from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'
import { StatCard } from '@/components/ui'
import { Users, Files, MessageSquare, Zap, Activity } from 'lucide-react'
import { formatNumber, formatTokens } from '@/utils/helpers'

export function DashboardPage() {
  const { user } = useAuthStore()
  const isAdmin = user?.role === 'admin'
  const { data: metrics, isLoading } = useSystemMetrics()

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Welcome back, {user?.full_name || user?.username}
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">Here's an overview of your research workspace</p>
        </div>

        {/* Personal stats */}
        <div>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Your Activity</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <StatCard label="Total Queries" value={formatNumber(user?.total_queries || 0)} icon={<MessageSquare size={18} />} />
            <StatCard label="Tokens Used" value={formatTokens(user?.total_tokens_used || 0)} icon={<Zap size={18} />} />
            <StatCard label="Documents Uploaded" value={formatNumber(user?.total_documents_uploaded || 0)} icon={<Files size={18} />} />
          </div>
        </div>

        {/* System metrics (admin only) */}
        {isAdmin && (
          <div>
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">System Metrics</h2>
            {isLoading ? (
              <div className="flex justify-center py-10"><Spinner /></div>
            ) : metrics ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard label="Total Users" value={formatNumber(metrics.users?.total || 0)} icon={<Users size={18} />} color="text-blue-600" />
                <StatCard label="Total Documents" value={formatNumber(metrics.documents?.total || 0)} icon={<Files size={18} />} color="text-green-600" />
                <StatCard label="Total Conversations" value={formatNumber(metrics.conversations?.total || 0)} icon={<MessageSquare size={18} />} color="text-purple-600" />
                <StatCard label="Avg Latency" value={`${metrics.performance?.avg_latency_ms?.toFixed(0) || 0}ms`} icon={<Activity size={18} />} color="text-orange-600" />
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  )
}

// ============================================================
// Settings Page
// ============================================================
import { authAPI } from '@/services/api'
import toast from 'react-hot-toast'

export function SettingsPage() {
  const { user, updateUser } = useAuthStore()
  const [fullName, setFullName] = useState(user?.full_name || '')
  const [saving, setSaving] = useState(false)
  const [pwForm, setPwForm] = useState({ current_password: '', new_password: '' })
  const [changingPw, setChangingPw] = useState(false)
  const [generatingKey, setGeneratingKey] = useState(false)
  const [apiKey, setApiKey] = useState<string | null>(null)

  const handleSaveProfile = async () => {
    setSaving(true)
    try {
      await authAPI.updateMe({ full_name: fullName })
      updateUser({ full_name: fullName })
      toast.success('Profile updated')
    } catch { toast.error('Failed to update') }
    finally { setSaving(false) }
  }

  const handleChangePassword = async () => {
    if (!pwForm.current_password || !pwForm.new_password) return
    setChangingPw(true)
    try {
      await authAPI.changePassword(pwForm)
      toast.success('Password changed')
      setPwForm({ current_password: '', new_password: '' })
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || 'Failed')
    } finally { setChangingPw(false) }
  }

  const handleGenerateKey = async () => {
    setGeneratingKey(true)
    try {
      const { data } = await authAPI.generateApiKey()
      setApiKey(data.api_key)
    } catch { toast.error('Failed') }
    finally { setGeneratingKey(false) }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Settings</h1>

        <Card className="p-6 space-y-4">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">Profile</h2>
          <Input label="Full Name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          <Input label="Email" value={user?.email || ''} disabled />
          <Input label="Username" value={user?.username || ''} disabled />
          <Button loading={saving} onClick={handleSaveProfile}>Save Changes</Button>
        </Card>

        <Card className="p-6 space-y-4">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">Change Password</h2>
          <Input label="Current Password" type="password" value={pwForm.current_password} onChange={(e) => setPwForm({ ...pwForm, current_password: e.target.value })} />
          <Input label="New Password" type="password" value={pwForm.new_password} onChange={(e) => setPwForm({ ...pwForm, new_password: e.target.value })} hint="Min 8 chars, 1 uppercase, 1 number" />
          <Button loading={changingPw} onClick={handleChangePassword}>Update Password</Button>
        </Card>

        <Card className="p-6 space-y-4">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">API Key</h2>
          <p className="text-sm text-gray-500">Generate an API key for programmatic access.</p>
          {apiKey && (
            <div className="p-3 bg-gray-50 dark:bg-gray-700 rounded-lg font-mono text-xs break-all text-gray-700 dark:text-gray-300 select-all">
              {apiKey}
            </div>
          )}
          <Button loading={generatingKey} onClick={handleGenerateKey} variant="outline">
            {apiKey ? 'Regenerate API Key' : 'Generate API Key'}
          </Button>
        </Card>
      </div>
    </div>
  )
}

// ============================================================
// Admin Page
// ============================================================
import { useAdminUsers } from '@/hooks/useApi'
import { Shield, UserCheck, UserX } from 'lucide-react'
import { adminAPI } from '@/services/api'

export function AdminPage() {
  const [page, setPage] = useState(1)
  const { data, isLoading, refetch } = useAdminUsers({ page })
  const users: { id: string; email: string; username: string; role: string; is_active: boolean; total_queries: number }[] = data?.users || []

  const handleToggleActive = async (id: string, isActive: boolean) => {
    await adminAPI.updateUser(id, { is_active: !isActive })
    refetch()
    toast.success(`User ${isActive ? 'deactivated' : 'activated'}`)
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
        <div className="flex items-center gap-3">
          <Shield size={24} className="text-primary-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Admin Panel</h1>
        </div>

        <Card>
          <div className="p-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-base font-semibold text-gray-900 dark:text-white">User Management</h2>
          </div>
          {isLoading ? (
            <div className="flex justify-center py-12"><Spinner /></div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-500 border-b border-gray-100 dark:border-gray-700">
                    {['User','Email','Role','Queries','Status','Actions'].map(h => (
                      <th key={h} className="px-4 py-3 font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                  {users.map((u) => (
                    <tr key={u.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{u.username}</td>
                      <td className="px-4 py-3 text-gray-500">{u.email}</td>
                      <td className="px-4 py-3"><Badge variant={u.role === 'admin' ? 'danger' : 'default'}>{u.role}</Badge></td>
                      <td className="px-4 py-3 text-gray-500">{u.total_queries}</td>
                      <td className="px-4 py-3">
                        <Badge variant={u.is_active ? 'success' : 'danger'}>{u.is_active ? 'Active' : 'Inactive'}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => handleToggleActive(u.id, u.is_active)}
                          className={cn('p-1.5 rounded transition-colors', u.is_active ? 'text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20' : 'text-green-400 hover:bg-green-50 dark:hover:bg-green-900/20')}
                        >
                          {u.is_active ? <UserX size={14} /> : <UserCheck size={14} />}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
