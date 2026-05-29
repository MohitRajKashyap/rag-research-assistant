// API base URL
export const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

// File upload
export const MAX_FILE_SIZE_MB = 50
export const ALLOWED_EXTENSIONS = ['pdf', 'docx', 'txt', 'md']
export const ALLOWED_MIME_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
  'text/markdown',
]

// Pagination
export const DEFAULT_PAGE_SIZE = 20

// Document status labels
export const STATUS_LABELS: Record<string, string> = {
  pending: 'Queued',
  processing: 'Processing',
  indexed: 'Indexed',
  failed: 'Failed',
}

export const STATUS_COLORS: Record<string, string> = {
  pending: 'text-yellow-600 bg-yellow-50 dark:bg-yellow-900/20',
  processing: 'text-blue-600 bg-blue-50 dark:bg-blue-900/20',
  indexed: 'text-green-600 bg-green-50 dark:bg-green-900/20',
  failed: 'text-red-600 bg-red-50 dark:bg-red-900/20',
}

export const DOC_TYPE_ICONS: Record<string, string> = {
  pdf: '📄',
  docx: '📝',
  txt: '📃',
  md: '📋',
}
