import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, FileText, Trash2, RefreshCw, Eye,
  CheckCircle, Clock, AlertCircle, Loader2, Filter, X,
} from 'lucide-react'
import { useDocuments, useDeleteDocument } from '@/hooks/useApi'
import { documentsAPI } from '@/services/api'
import { Button, Badge, Card, Spinner, EmptyState } from '@/components/ui'
import { formatFileSize, formatRelativeTime, truncate } from '@/utils/helpers'
import { DOC_TYPE_ICONS, STATUS_LABELS } from '@/utils/constants'
import { Document } from '@/types'
import toast from 'react-hot-toast'
import { cn } from '@/utils/helpers'

export default function DocumentsPage() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const { data, isLoading, refetch } = useDocuments({ page, page_size: 20, status: statusFilter || undefined })
  const deleteDoc = useDeleteDocument()
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<string[]>([])

  const onDrop = useCallback(async (accepted: File[]) => {
    if (!accepted.length) return
    setUploading(true)
    setUploadProgress([`Uploading ${accepted.length} file(s)...`])

    const formData = new FormData()
    accepted.forEach((f) => formData.append('files', f))

    try {
      const { data: result } = await documentsAPI.upload(formData)
      toast.success(`${result.total_uploaded} file(s) queued for processing`)
      if (result.total_failed > 0) {
        result.failed.forEach((f: { filename: string; error: string }) =>
          toast.error(`${f.filename}: ${f.error}`)
        )
      }
      refetch()
    } catch (err: unknown) {
      toast.error('Upload failed')
    } finally {
      setUploading(false)
      setUploadProgress([])
    }
  }, [refetch])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
    },
    maxSize: 50 * 1024 * 1024,
  })

  const docs = data?.documents || []
  const total = data?.total || 0

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Documents</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
              {total} document{total !== 1 ? 's' : ''} · Upload PDFs, DOCX, TXT, or Markdown
            </p>
          </div>
          <Button onClick={() => refetch()} variant="outline" size="sm" icon={<RefreshCw size={14} />}>
            Refresh
          </Button>
        </div>

        {/* Upload dropzone */}
        <div
          {...getRootProps()}
          className={cn(
            'border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all',
            isDragActive
              ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
              : 'border-gray-300 dark:border-gray-600 hover:border-primary-400 hover:bg-gray-50 dark:hover:bg-gray-800',
          )}
        >
          <input {...getInputProps()} />
          {uploading ? (
            <div className="flex flex-col items-center gap-3">
              <Loader2 size={32} className="animate-spin text-primary-600" />
              <p className="text-sm text-gray-600 dark:text-gray-400">{uploadProgress[0]}</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <div className="w-12 h-12 bg-primary-100 dark:bg-primary-900/30 rounded-xl flex items-center justify-center">
                <Upload size={22} className="text-primary-600" />
              </div>
              <div>
                <p className="font-semibold text-gray-900 dark:text-white">
                  {isDragActive ? 'Drop files here' : 'Drag & drop or click to upload'}
                </p>
                <p className="text-sm text-gray-500 mt-0.5">PDF, DOCX, TXT, MD · Max 50MB each</p>
              </div>
            </div>
          )}
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2">
          <Filter size={14} className="text-gray-400" />
          {['', 'pending', 'processing', 'indexed', 'failed'].map((s) => (
            <button
              key={s}
              onClick={() => { setStatusFilter(s); setPage(1) }}
              className={cn(
                'px-3 py-1 rounded-full text-xs font-medium transition-colors',
                statusFilter === s
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600',
              )}
            >
              {s ? STATUS_LABELS[s] : 'All'}
            </button>
          ))}
        </div>

        {/* Document list */}
        {isLoading ? (
          <div className="flex justify-center py-20"><Spinner size={32} /></div>
        ) : docs.length === 0 ? (
          <EmptyState
            icon={<FileText size={48} />}
            title="No documents yet"
            description="Upload research papers to start asking questions about them."
          />
        ) : (
          <div className="space-y-2">
            <AnimatePresence>
              {docs.map((doc) => (
                <DocRow
                  key={doc.id}
                  doc={doc}
                  onDelete={() => deleteDoc.mutate(doc.id)}
                />
              ))}
            </AnimatePresence>
          </div>
        )}

        {/* Pagination */}
        {data && data.total_pages > 1 && (
          <div className="flex justify-center gap-2">
            <Button
              variant="outline" size="sm"
              disabled={page === 1}
              onClick={() => setPage(p => p - 1)}
            >Previous</Button>
            <span className="px-4 py-1.5 text-sm text-gray-600 dark:text-gray-400">
              {page} / {data.total_pages}
            </span>
            <Button
              variant="outline" size="sm"
              disabled={page >= data.total_pages}
              onClick={() => setPage(p => p + 1)}
            >Next</Button>
          </div>
        )}
      </div>
    </div>
  )
}

function DocRow({ doc, onDelete }: { doc: Document; onDelete: () => void }) {
  const statusIcons = {
    pending: <Clock size={14} className="text-yellow-500" />,
    processing: <Loader2 size={14} className="text-blue-500 animate-spin" />,
    indexed: <CheckCircle size={14} className="text-green-500" />,
    failed: <AlertCircle size={14} className="text-red-500" />,
  }
  const statusVariants: Record<string, 'default' | 'success' | 'warning' | 'danger' | 'info'> = {
    pending: 'warning', processing: 'info', indexed: 'success', failed: 'danger',
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -5 }}
    >
      <Card className="px-4 py-3 hover:shadow-md transition-shadow">
        <div className="flex items-center gap-3">
          <span className="text-xl flex-shrink-0">{DOC_TYPE_ICONS[doc.doc_type] || '📄'}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                {doc.title || doc.original_filename}
              </p>
              {statusIcons[doc.status]}
            </div>
            <div className="flex items-center gap-3 mt-0.5">
              <span className="text-xs text-gray-400">{formatFileSize(doc.file_size)}</span>
              {doc.total_pages && <span className="text-xs text-gray-400">{doc.total_pages} pages</span>}
              {doc.chunk_count > 0 && <span className="text-xs text-gray-400">{doc.chunk_count} chunks</span>}
              <span className="text-xs text-gray-400">{formatRelativeTime(doc.created_at)}</span>
            </div>
          </div>
          <Badge variant={statusVariants[doc.status]}>{STATUS_LABELS[doc.status]}</Badge>
          <button
            onClick={onDelete}
            className="p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </Card>
    </motion.div>
  )
}
