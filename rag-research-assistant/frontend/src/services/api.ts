import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios'
import toast from 'react-hot-toast'

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor — inject auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// Response interceptor — handle 401 with token refresh
let isRefreshing = false
let failedQueue: Array<{ resolve: (token: string) => void; reject: (err: unknown) => void }> = []

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error)
    else resolve(token!)
  })
  failedQueue = []
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return api(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) {
        isRefreshing = false
        localStorage.clear()
        window.location.href = '/login'
        return Promise.reject(error)
      }

      try {
        const response = await axios.post(`${BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        })
        const { access_token, refresh_token } = response.data
        localStorage.setItem('access_token', access_token)
        localStorage.setItem('refresh_token', refresh_token)
        api.defaults.headers.common.Authorization = `Bearer ${access_token}`
        processQueue(null, access_token)
        originalRequest.headers.Authorization = `Bearer ${access_token}`
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        localStorage.clear()
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // Show error toasts for non-auth errors
    if (error.response?.status !== 401) {
      const detail = (error.response?.data as { detail?: string })?.detail
      if (detail && error.response?.status !== 422) {
        toast.error(detail)
      }
    }

    return Promise.reject(error)
  },
)

export default api

// -------------------------------------------------------
// Auth API
// -------------------------------------------------------
export const authAPI = {
  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data),
  signup: (data: { email: string; username: string; password: string; full_name?: string }) =>
    api.post('/auth/signup', data),
  refresh: (refresh_token: string) =>
    api.post('/auth/refresh', { refresh_token }),
  getMe: () => api.get('/auth/me'),
  updateMe: (data: Record<string, string>) => api.put('/auth/me', data),
  changePassword: (data: { current_password: string; new_password: string }) =>
    api.post('/auth/change-password', data),
  generateApiKey: () => api.post('/auth/api-key'),
}

// -------------------------------------------------------
// Documents API
// -------------------------------------------------------
export const documentsAPI = {
  upload: (formData: FormData) =>
    api.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  list: (params?: { page?: number; page_size?: number; status?: string; collection_id?: string }) =>
    api.get('/documents/', { params }),
  get: (id: string) => api.get(`/documents/${id}`),
  getStatus: (id: string) => api.get(`/documents/${id}/status`),
  update: (id: string, data: Record<string, unknown>) => api.put(`/documents/${id}`, data),
  delete: (id: string) => api.delete(`/documents/${id}`),
  search: (data: { query: string; top_k?: number; score_threshold?: number; collection_id?: string }) =>
    api.post('/documents/search', data),
  getChunks: (id: string) => api.get(`/documents/${id}/chunks`),
}

// -------------------------------------------------------
// Chat API
// -------------------------------------------------------
export const chatAPI = {
  send: (data: {
    message: string
    conversation_id?: string
    collection_id?: string
    top_k?: number
  }) => api.post('/chat/', data),
  listConversations: (params?: { page?: number; page_size?: number; include_archived?: boolean }) =>
    api.get('/chat/conversations', { params }),
  getConversation: (id: string) => api.get(`/chat/conversations/${id}`),
  updateConversation: (id: string, data: { title?: string; is_archived?: boolean }) =>
    api.put(`/chat/conversations/${id}`, data),
  deleteConversation: (id: string) => api.delete(`/chat/conversations/${id}`),
  feedback: (messageId: string, rating: number) =>
    api.post(`/chat/messages/${messageId}/feedback`, { rating }),
  toggleBookmark: (messageId: string) =>
    api.post(`/chat/messages/${messageId}/bookmark`),
}

// -------------------------------------------------------
// Collections API
// -------------------------------------------------------
export const collectionsAPI = {
  create: (data: { name: string; description?: string; color?: string }) =>
    api.post('/collections/', data),
  list: () => api.get('/collections/'),
  get: (id: string) => api.get(`/collections/${id}`),
  update: (id: string, data: Record<string, unknown>) => api.put(`/collections/${id}`, data),
  delete: (id: string) => api.delete(`/collections/${id}`),
}

// -------------------------------------------------------
// Admin API
// -------------------------------------------------------
export const adminAPI = {
  getMetrics: () => api.get('/admin/metrics'),
  listUsers: (params?: { page?: number; page_size?: number; role?: string }) =>
    api.get('/admin/users', { params }),
  getUser: (id: string) => api.get(`/admin/users/${id}`),
  updateUser: (id: string, data: Record<string, unknown>) => api.put(`/admin/users/${id}`, data),
  listDocuments: (params?: { page?: number; page_size?: number }) =>
    api.get('/admin/documents', { params }),
  getVectorStore: () => api.get('/admin/vector-store'),
}

// -------------------------------------------------------
// Health API
// -------------------------------------------------------
export const healthAPI = {
  check: () => api.get('/health'),
}
