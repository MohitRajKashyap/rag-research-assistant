import { create } from 'zustand'
import { Conversation, Message, MessageSource, StreamChunk } from '@/types'
import { chatAPI } from '@/services/api'
import { BASE_URL } from '@/utils/constants'

interface ChatState {
  conversations: Conversation[]
  activeConversationId: string | null
  messages: Message[]
  isStreaming: boolean
  streamingContent: string
  streamingSources: MessageSource[]
  isLoadingConversations: boolean
  isLoadingMessages: boolean
  error: string | null

  // Actions
  loadConversations: () => Promise<void>
  loadMessages: (conversationId: string) => Promise<void>
  setActiveConversation: (id: string | null) => void
  sendMessage: (message: string, collectionId?: string) => Promise<void>
  sendMessageStream: (message: string, collectionId?: string) => Promise<void>
  deleteConversation: (id: string) => Promise<void>
  renameConversation: (id: string, title: string) => Promise<void>
  newConversation: () => void
  addOptimisticMessage: (content: string) => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  activeConversationId: null,
  messages: [],
  isStreaming: false,
  streamingContent: '',
  streamingSources: [],
  isLoadingConversations: false,
  isLoadingMessages: false,
  error: null,

  loadConversations: async () => {
    set({ isLoadingConversations: true })
    try {
      const { data } = await chatAPI.listConversations({ page_size: 50 })
      set({ conversations: data.conversations, isLoadingConversations: false })
    } catch {
      set({ isLoadingConversations: false })
    }
  },

  loadMessages: async (conversationId) => {
    set({ isLoadingMessages: true })
    try {
      const { data } = await chatAPI.getConversation(conversationId)
      set({
        messages: data.messages || [],
        activeConversationId: conversationId,
        isLoadingMessages: false,
      })
    } catch {
      set({ isLoadingMessages: false })
    }
  },

  setActiveConversation: (id) => {
    set({ activeConversationId: id, messages: [], streamingContent: '', streamingSources: [] })
    if (id) get().loadMessages(id)
  },

  newConversation: () => {
    set({
      activeConversationId: null,
      messages: [],
      streamingContent: '',
      streamingSources: [],
      error: null,
    })
  },

  addOptimisticMessage: (content) => {
    const optimistic: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content,
      sources: [],
      is_bookmarked: false,
      created_at: new Date().toISOString(),
    }
    set((state) => ({ messages: [...state.messages, optimistic] }))
  },

  sendMessage: async (message, collectionId) => {
    get().addOptimisticMessage(message)
    set({ isStreaming: true, error: null })

    try {
      const { data } = await chatAPI.send({
        message,
        conversation_id: get().activeConversationId || undefined,
        collection_id: collectionId,
        top_k: 5,
      })

      const assistantMsg: Message = {
        id: data.message_id,
        role: 'assistant',
        content: data.content,
        sources: data.sources,
        tokens_used: data.tokens_used,
        latency_ms: data.latency_ms,
        model_used: data.model_used,
        is_bookmarked: false,
        created_at: new Date().toISOString(),
      }

      set((state) => ({
        messages: [...state.messages, assistantMsg],
        activeConversationId: data.conversation_id,
        isStreaming: false,
      }))

      // Refresh conversation list
      get().loadConversations()
    } catch (err) {
      set({ isStreaming: false, error: 'Failed to get response. Please try again.' })
    }
  },

  sendMessageStream: async (message, collectionId) => {
    get().addOptimisticMessage(message)
    set({ isStreaming: true, streamingContent: '', streamingSources: [], error: null })

    const token = localStorage.getItem('access_token')
    const conversationId = get().activeConversationId

    try {
      const response = await fetch(`${BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message,
          conversation_id: conversationId || undefined,
          collection_id: collectionId || undefined,
          top_k: 5,
          stream: true,
        }),
      })

      if (!response.ok) throw new Error('Stream request failed')

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let fullContent = ''
      let newConversationId = conversationId

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value)
        const lines = text.split('\n').filter((l) => l.startsWith('data: '))

        for (const line of lines) {
          try {
            const chunk: StreamChunk = JSON.parse(line.replace('data: ', ''))

            if (chunk.type === 'init' && chunk.conversation_id) {
              newConversationId = chunk.conversation_id
              set({ activeConversationId: chunk.conversation_id })
            } else if (chunk.type === 'sources') {
              set({ streamingSources: chunk.sources || [] })
            } else if (chunk.type === 'token') {
              fullContent += chunk.content || ''
              set({ streamingContent: fullContent })
            } else if (chunk.type === 'done') {
              const finalMsg: Message = {
                id: chunk.message_id || `msg-${Date.now()}`,
                role: 'assistant',
                content: fullContent,
                sources: get().streamingSources,
                is_bookmarked: false,
                created_at: new Date().toISOString(),
              }
              set((state) => ({
                messages: [...state.messages, finalMsg],
                isStreaming: false,
                streamingContent: '',
                streamingSources: [],
              }))
              get().loadConversations()
            } else if (chunk.type === 'error') {
              set({ isStreaming: false, error: chunk.error || 'Stream error' })
            }
          } catch {
            // Skip malformed chunks
          }
        }
      }
    } catch (err) {
      set({ isStreaming: false, error: 'Connection error. Please try again.' })
    }
  },

  deleteConversation: async (id) => {
    await chatAPI.deleteConversation(id)
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
      activeConversationId: state.activeConversationId === id ? null : state.activeConversationId,
      messages: state.activeConversationId === id ? [] : state.messages,
    }))
  },

  renameConversation: async (id, title) => {
    await chatAPI.updateConversation(id, { title })
    set((state) => ({
      conversations: state.conversations.map((c) => (c.id === id ? { ...c, title } : c)),
    }))
  },
}))
