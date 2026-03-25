'use client'

import { create } from 'zustand'
import type { Source } from '@/types/api'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  isError?: boolean
}

interface ChatState {
  messages: ChatMessage[]
  isLoading: boolean
  addUserMessage: (content: string) => string
  addAssistantMessage: (content: string, sources?: Source[]) => void
  addErrorMessage: (content: string) => void
  setLoading: (loading: boolean) => void
  clearMessages: () => void
}

let idCounter = 0
const genId = () => `msg-${(++idCounter).toString()}-${Date.now().toString()}`

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isLoading: false,

  addUserMessage: (content) => {
    const id = genId()
    set((state) => ({
      messages: [...state.messages, { id, role: 'user', content }],
    }))
    return id
  },

  addAssistantMessage: (content, sources) => {
    set((state) => ({
      messages: [
        ...state.messages,
        { id: genId(), role: 'assistant', content, sources },
      ],
    }))
  },

  addErrorMessage: (content) => {
    set((state) => ({
      messages: [
        ...state.messages,
        { id: genId(), role: 'assistant', content, isError: true },
      ],
    }))
  },

  setLoading: (isLoading) => set({ isLoading }),

  clearMessages: () => set({ messages: [] }),
}))
