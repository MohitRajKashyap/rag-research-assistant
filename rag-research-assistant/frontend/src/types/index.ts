// ============================================================
// Global TypeScript Types
// ============================================================

export interface User {
  id: string
  email: string
  username: string
  full_name?: string
  role: 'user' | 'admin' | 'researcher'
  is_active: boolean
  is_verified: boolean
  total_queries: number
  total_tokens_used: number
  total_documents_uploaded: number
  created_at: string
  last_login_at?: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface LoginRequest {
  email: string
  password: string
}

export interface SignupRequest {
  email: string
  username: string
  password: string
  full_name?: string
}

// Documents
export type DocumentStatus = 'pending' | 'processing' | 'indexed' | 'failed'
export type DocumentType = 'pdf' | 'docx' | 'txt' | 'md'

export interface Document {
  id: string
  filename: string
  original_filename: string
  file_size: number
  doc_type: DocumentType
  title?: string
  description?: string
  author?: string
  total_pages?: number
  total_words?: number
  status: DocumentStatus
  chunk_count: number
  is_indexed: boolean
  collection_id?: string
  created_at: string
  indexed_at?: string
}

export interface DocumentListResponse {
  documents: Document[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface UploadResponse {
  document_id: string
  filename: string
  status: DocumentStatus
  task_id: string
  message: string
}

export interface BatchUploadResponse {
  uploaded: UploadResponse[]
  failed: { filename: string; error: string }[]
  total_uploaded: number
  total_failed: number
}

export interface SearchResult {
  document_id: string
  document_title: string
  chunk_content: string
  chunk_index: number
  page_number?: number
  similarity_score: number
  filename: string
}

export interface DocumentSearchResponse {
  query: string
  results: SearchResult[]
  total_results: number
  search_latency_ms: number
}

// Chat & Conversations
export type MessageRole = 'user' | 'assistant' | 'system'

export interface MessageSource {
  document_id: string
  document_title: string
  filename: string
  chunk_content: string
  chunk_index: number
  page_number?: number
  similarity_score: number
}

export interface Message {
  id: string
  role: MessageRole
  content: string
  sources: MessageSource[]
  tokens_used?: number
  latency_ms?: number
  model_used?: string
  is_bookmarked: boolean
  feedback_rating?: number
  created_at: string
}

export interface Conversation {
  id: string
  title?: string
  message_count: number
  total_tokens: number
  is_archived: boolean
  created_at: string
  updated_at: string
  messages?: Message[]
}

export interface ConversationListResponse {
  conversations: Conversation[]
  total: number
  page: number
  page_size: number
}

export interface ChatRequest {
  message: string
  conversation_id?: string
  collection_id?: string
  top_k?: number
  stream?: boolean
}

export interface ChatResponse {
  message_id: string
  conversation_id: string
  role: MessageRole
  content: string
  sources: MessageSource[]
  tokens_used: number
  latency_ms: number
  model_used: string
}

// Stream chunks
export type StreamChunkType = 'init' | 'sources' | 'token' | 'done' | 'error'

export interface StreamChunk {
  type: StreamChunkType
  content?: string
  sources?: MessageSource[]
  conversation_id?: string
  message_id?: string
  error?: string
}

// Collections
export interface Collection {
  id: string
  name: string
  description?: string
  color: string
  icon: string
  document_count: number
}

// Analytics
export interface SystemMetrics {
  users: { total: number; active: number }
  documents: { total: number; indexed: number }
  conversations: { total: number }
  messages: { total: number; total_tokens: number }
  performance: { avg_latency_ms: number }
  vector_store: Record<string, unknown>
}

// API
export interface APIError {
  detail: string
  success?: boolean
  code?: string
}

export interface SuccessResponse {
  success: boolean
  message: string
  data?: unknown
}

export interface PaginationParams {
  page?: number
  page_size?: number
}
