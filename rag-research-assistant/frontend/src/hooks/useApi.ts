import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { documentsAPI, collectionsAPI, adminAPI, healthAPI } from '@/services/api'
import { useAuthStore } from '@/store/authStore'
import toast from 'react-hot-toast'

// -------------------------------------------------------
// Auth hooks
// -------------------------------------------------------
export function useAuth() {
  return useAuthStore()
}

// -------------------------------------------------------
// Document hooks
// -------------------------------------------------------
export function useDocuments(params?: {
  page?: number
  page_size?: number
  status?: string
  collection_id?: string
}) {
  return useQuery({
    queryKey: ['documents', params],
    queryFn: () => documentsAPI.list(params).then((r) => r.data),
    staleTime: 30_000,
  })
}

export function useDocument(id: string | undefined) {
  return useQuery({
    queryKey: ['document', id],
    queryFn: () => documentsAPI.get(id!).then((r) => r.data),
    enabled: !!id,
  })
}

export function useDocumentStatus(id: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ['document-status', id],
    queryFn: () => documentsAPI.getStatus(id!).then((r) => r.data),
    enabled: !!id && enabled,
    refetchInterval: (data) => {
      if (!data) return 3000
      const status = (data as { status: string }).status
      return status === 'pending' || status === 'processing' ? 2000 : false
    },
  })
}

export function useDeleteDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => documentsAPI.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['documents'] })
      toast.success('Document deleted')
    },
    onError: () => toast.error('Failed to delete document'),
  })
}

export function useSearchDocuments() {
  return useMutation({
    mutationFn: (data: { query: string; top_k?: number; collection_id?: string }) =>
      documentsAPI.search(data).then((r) => r.data),
  })
}

// -------------------------------------------------------
// Collection hooks
// -------------------------------------------------------
export function useCollections() {
  return useQuery({
    queryKey: ['collections'],
    queryFn: () => collectionsAPI.list().then((r) => r.data),
    staleTime: 60_000,
  })
}

export function useCreateCollection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; description?: string; color?: string }) =>
      collectionsAPI.create(data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['collections'] })
      toast.success('Collection created')
    },
  })
}

export function useDeleteCollection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => collectionsAPI.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['collections'] })
      toast.success('Collection deleted')
    },
  })
}

// -------------------------------------------------------
// Admin hooks
// -------------------------------------------------------
export function useSystemMetrics() {
  return useQuery({
    queryKey: ['metrics'],
    queryFn: () => adminAPI.getMetrics().then((r) => r.data),
    refetchInterval: 30_000,
  })
}

export function useAdminUsers(params?: { page?: number; role?: string }) {
  return useQuery({
    queryKey: ['admin-users', params],
    queryFn: () => adminAPI.listUsers(params).then((r) => r.data),
  })
}

export function useVectorStoreStats() {
  return useQuery({
    queryKey: ['vector-store-stats'],
    queryFn: () => adminAPI.getVectorStore().then((r) => r.data),
    staleTime: 60_000,
  })
}

// -------------------------------------------------------
// Health hook
// -------------------------------------------------------
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => healthAPI.check().then((r) => r.data),
    refetchInterval: 60_000,
  })
}
