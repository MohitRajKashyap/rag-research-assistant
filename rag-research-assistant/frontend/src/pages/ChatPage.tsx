import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Send, Plus, Trash2, MessageSquare, ChevronRight,
  BookOpen, Loader2, ThumbsUp, ThumbsDown, Copy, Check,
  ExternalLink, Bot, User,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useChatStore } from '@/store/chatStore'
import { Button, Spinner, EmptyState } from '@/components/ui'
import { formatRelativeTime, truncate, copyToClipboard } from '@/utils/helpers'
import { chatAPI } from '@/services/api'
import { Message, MessageSource } from '@/types'
import toast from 'react-hot-toast'
import { cn } from '@/utils/helpers'

export default function ChatPage() {
  const {
    conversations, messages, activeConversationId, isStreaming,
    streamingContent, streamingSources, isLoadingMessages,
    loadConversations, setActiveConversation, sendMessageStream,
    deleteConversation, newConversation,
  } = useChatStore()

  const [input, setInput] = useState('')
  const [copied, setCopied] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => { loadConversations() }, [])
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, streamingContent])

  const handleSend = async () => {
    const msg = input.trim()
    if (!msg || isStreaming) return
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    await sendMessageStream(msg)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px'
  }

  const handleCopy = async (text: string, id: string) => {
    await copyToClipboard(text)
    setCopied(id)
    toast.success('Copied!')
    setTimeout(() => setCopied(null), 2000)
  }

  const handleBookmark = async (msgId: string) => {
    try {
      await chatAPI.toggleBookmark(msgId)
      toast.success('Bookmark toggled')
    } catch { /* silent */ }
  }

  return (
    <div className="flex h-full bg-gray-50 dark:bg-gray-950">
      {/* Conversation list */}
      <div className="w-64 flex-shrink-0 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 flex flex-col hidden lg:flex">
        <div className="p-3 border-b border-gray-200 dark:border-gray-700">
          <Button onClick={newConversation} variant="primary" size="sm" className="w-full" icon={<Plus size={15} />}>
            New Chat
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
          {conversations.length === 0 ? (
            <p className="text-xs text-gray-400 text-center py-8">No conversations yet</p>
          ) : (
            conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => setActiveConversation(conv.id)}
                className={cn(
                  'w-full text-left px-3 py-2.5 rounded-lg group flex items-start gap-2 transition-colors',
                  activeConversationId === conv.id
                    ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300'
                    : 'hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300',
                )}
              >
                <MessageSquare size={14} className="mt-0.5 flex-shrink-0 opacity-60" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium truncate">
                    {conv.title || 'New conversation'}
                  </p>
                  <p className="text-xs opacity-50">{formatRelativeTime(conv.updated_at)}</p>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteConversation(conv.id) }}
                  className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-red-100 dark:hover:bg-red-900/20 text-red-500 transition-all"
                >
                  <Trash2 size={12} />
                </button>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
          {!activeConversationId && messages.length === 0 ? (
            <WelcomeScreen />
          ) : isLoadingMessages ? (
            <div className="flex justify-center py-20"><Spinner size={32} /></div>
          ) : (
            <>
              {messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  onCopy={() => handleCopy(msg.content, msg.id)}
                  isCopied={copied === msg.id}
                  onBookmark={() => handleBookmark(msg.id)}
                />
              ))}

              {/* Streaming message */}
              {isStreaming && (
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center flex-shrink-0">
                    <Bot size={16} className="text-white" />
                  </div>
                  <div className="flex-1 bg-white dark:bg-gray-800 rounded-2xl rounded-tl-none px-5 py-4 shadow-sm border border-gray-100 dark:border-gray-700 max-w-3xl">
                    {streamingSources.length > 0 && (
                      <SourcesList sources={streamingSources} />
                    )}
                    {streamingContent ? (
                      <div className="prose prose-sm dark:prose-invert max-w-none">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingContent}</ReactMarkdown>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 text-gray-500">
                        <Loader2 size={14} className="animate-spin" />
                        <span className="text-sm">Researching...</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div className="px-4 pb-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-lg p-3">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleTextareaChange}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything about your research documents..."
              rows={1}
              className="w-full resize-none bg-transparent text-sm text-gray-900 dark:text-white placeholder:text-gray-400 focus:outline-none min-h-[40px] max-h-[200px] overflow-y-auto"
            />
            <div className="flex items-center justify-between pt-2 border-t border-gray-100 dark:border-gray-700">
              <p className="text-xs text-gray-400">Enter to send · Shift+Enter for new line</p>
              <Button
                onClick={handleSend}
                disabled={!input.trim() || isStreaming}
                loading={isStreaming}
                size="sm"
                icon={<Send size={14} />}
              >
                Send
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function WelcomeScreen() {
  return (
    <div className="flex flex-col items-center justify-center h-full py-20 px-4 text-center">
      <div className="w-16 h-16 bg-primary-100 dark:bg-primary-900/30 rounded-2xl flex items-center justify-center mb-4">
        <Bot size={32} className="text-primary-600" />
      </div>
      <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Research Assistant</h2>
      <p className="text-gray-500 dark:text-gray-400 max-w-md mb-8">
        Ask me anything about your uploaded research documents. I'll retrieve the most relevant context and give you accurate, cited answers.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg w-full">
        {[
          'Summarize the key findings in my documents',
          'What methodology is used in the research?',
          'Compare the results across different papers',
          'What are the main limitations mentioned?',
        ].map((q) => (
          <button
            key={q}
            className="text-left p-3 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 text-sm text-gray-700 dark:text-gray-300 hover:border-primary-300 hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-colors"
          >
            <ChevronRight size={14} className="inline mr-1 text-primary-500" />
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}

function MessageBubble({
  message, onCopy, isCopied, onBookmark,
}: { message: Message; onCopy: () => void; isCopied: boolean; onBookmark: () => void }) {
  const isUser = message.role === 'user'

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn('flex gap-3', isUser && 'flex-row-reverse')}
    >
      <div className={cn(
        'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
        isUser ? 'bg-gray-200 dark:bg-gray-700' : 'bg-primary-600',
      )}>
        {isUser ? <User size={15} className="text-gray-600 dark:text-gray-400" /> : <Bot size={15} className="text-white" />}
      </div>

      <div className={cn('max-w-3xl', isUser ? 'items-end' : 'items-start', 'flex flex-col gap-1')}>
        <div className={cn(
          'px-5 py-4 rounded-2xl shadow-sm text-sm',
          isUser
            ? 'bg-primary-600 text-white rounded-tr-none'
            : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-white border border-gray-100 dark:border-gray-700 rounded-tl-none',
        )}>
          {!isUser && message.sources && message.sources.length > 0 && (
            <SourcesList sources={message.sources} />
          )}
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>

        {/* Message meta */}
        {!isUser && (
          <div className="flex items-center gap-2 px-1">
            <span className="text-xs text-gray-400">{formatRelativeTime(message.created_at)}</span>
            {message.latency_ms && (
              <span className="text-xs text-gray-400">· {message.latency_ms}ms</span>
            )}
            <button onClick={onCopy} className="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
              {isCopied ? <Check size={12} className="text-green-500" /> : <Copy size={12} />}
            </button>
            <button onClick={onBookmark} className="p-1 rounded text-gray-400 hover:text-yellow-500 hover:bg-yellow-50 dark:hover:bg-yellow-900/20 transition-colors">
              <BookOpen size={12} />
            </button>
          </div>
        )}
      </div>
    </motion.div>
  )
}

function SourcesList({ sources }: { sources: MessageSource[] }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="mb-3 p-2 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-800">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-xs font-medium text-blue-700 dark:text-blue-300 hover:opacity-80"
      >
        <BookOpen size={12} />
        {sources.length} source{sources.length !== 1 ? 's' : ''} cited
        <ChevronRight size={12} className={cn('transition-transform', expanded && 'rotate-90')} />
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden mt-2 space-y-1.5"
          >
            {sources.map((s, i) => (
              <div key={i} className="bg-white dark:bg-gray-800 rounded p-2 text-xs">
                <div className="flex items-start justify-between gap-2">
                  <span className="font-semibold text-gray-800 dark:text-gray-200 truncate">{s.document_title}</span>
                  <span className="text-green-600 font-mono flex-shrink-0">{(s.similarity_score * 100).toFixed(0)}%</span>
                </div>
                <p className="text-gray-500 mt-0.5 line-clamp-2">{s.chunk_content}</p>
                {s.page_number && (
                  <span className="text-gray-400">p.{s.page_number}</span>
                )}
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
