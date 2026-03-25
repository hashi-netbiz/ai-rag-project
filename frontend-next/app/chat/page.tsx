'use client'

import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'motion/react'
import { Send, LogOut, Building2, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { MessageBubble } from '@/components/MessageBubble'
import { TypingIndicator } from '@/components/TypingIndicator'
import { RoleBadge } from '@/components/RoleBadge'
import { ThemeToggle } from '@/components/ThemeToggle'
import { useAuthStore } from '@/stores/authStore'
import { useChatStore } from '@/stores/chatStore'
import { apiChatQuery } from '@/lib/apiClient'
import { ROLE_SUGGESTIONS } from '@/lib/constants'

export default function ChatPage() {
  const router = useRouter()
  const { user, isAuthenticated, clearAuth, hydrateFromStorage } = useAuthStore()
  const {
    messages,
    isLoading,
    addUserMessage,
    addAssistantMessage,
    addErrorMessage,
    setLoading,
    clearMessages,
  } = useChatStore()

  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    hydrateFromStorage()
  }, [hydrateFromStorage])

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace('/')
    }
  }, [isAuthenticated, router])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const handleLogout = () => {
    clearAuth()
    clearMessages()
    router.push('/')
  }

  const sendQuery = async (query: string) => {
    const trimmed = query.trim()
    if (!trimmed || isLoading) return

    setInput('')
    addUserMessage(trimmed)
    setLoading(true)

    try {
      const result = await apiChatQuery(trimmed)
      addAssistantMessage(result.answer, result.sources)
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Something went wrong. Please try again.'
      if (msg.includes('Session expired') || msg.includes('401')) {
        clearAuth()
        router.push('/')
        return
      }
      addErrorMessage(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    void sendQuery(input)
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void sendQuery(input)
    }
  }

  const suggestions =
    user ? (ROLE_SUGGESTIONS[user.role] ?? ROLE_SUGGESTIONS['employee'] ?? []) : []

  if (!user) return null

  return (
    <>
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 border-r border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center gap-2">
            <Building2 size={18} className="text-blue-600" />
            <span className="font-semibold text-sm">Company Assistant</span>
          </div>
          <ThemeToggle />
        </div>

        <div className="px-4 py-4 space-y-2">
          <p className="text-xs text-neutral-500 dark:text-neutral-400 uppercase tracking-wider font-medium">
            Signed in as
          </p>
          <p className="text-sm font-medium truncate">{user.username}</p>
          <RoleBadge role={user.role} />
        </div>

        <Separator />

        <div className="flex-1 px-4 py-3">
          <p className="text-xs text-neutral-400 dark:text-neutral-600">
            Conversation history coming soon
          </p>
        </div>

        <div className="px-4 py-4 space-y-2 border-t border-neutral-200 dark:border-neutral-800">
          <Button
            variant="ghost"
            size="sm"
            onClick={clearMessages}
            className="w-full justify-start gap-2 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100"
          >
            <Trash2 size={14} />
            Clear chat
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            className="w-full justify-start gap-2 text-neutral-600 dark:text-neutral-400 hover:text-red-600 dark:hover:text-red-400"
          >
            <LogOut size={14} />
            Sign out
          </Button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 flex flex-col overflow-hidden bg-neutral-50 dark:bg-neutral-950">
        <div className="flex items-center justify-between px-6 py-3 bg-white dark:bg-neutral-900 border-b border-neutral-200 dark:border-neutral-800 shadow-sm">
          <div>
            <h1 className="text-sm font-semibold">Knowledge Base Chat</h1>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              Answers grounded in documents you are authorized to see
            </p>
          </div>
          <RoleBadge role={user.role} />
        </div>

        <ScrollArea className="flex-1 px-6 py-4">
          <AnimatePresence initial={false}>
            {messages.length === 0 ? (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex flex-col items-center justify-center min-h-[400px] text-center"
              >
                <Building2
                  size={40}
                  className="text-neutral-300 dark:text-neutral-700 mb-4"
                />
                <h2 className="text-base font-medium text-neutral-700 dark:text-neutral-300 mb-1">
                  Welcome, {user.username}
                </h2>
                <p className="text-sm text-neutral-400 dark:text-neutral-500 mb-6 max-w-xs">
                  You have access to{' '}
                  <span className="font-medium capitalize">
                    {user.role.replace('_', ' ')}
                  </span>{' '}
                  documents. Ask anything.
                </p>
                <div className="space-y-2 w-full max-w-sm">
                  {suggestions.map((s) => (
                    <button
                      key={s}
                      onClick={() => void sendQuery(s)}
                      className="w-full text-left text-sm px-4 py-2.5 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 hover:bg-neutral-50 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300 transition-colors"
                      type="button"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </motion.div>
            ) : (
              messages.map((msg) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <MessageBubble message={msg} />
                </motion.div>
              ))
            )}
          </AnimatePresence>

          {isLoading && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex justify-start mb-4"
            >
              <TypingIndicator />
            </motion.div>
          )}

          <div ref={bottomRef} />
        </ScrollArea>

        <div className="px-6 py-4 bg-white dark:bg-neutral-900 border-t border-neutral-200 dark:border-neutral-800">
          <form onSubmit={handleSubmit} className="flex gap-3 items-end">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={`Ask about ${user.role.replace('_', ' ')} information…`}
              disabled={isLoading}
              rows={1}
              className="flex-1 resize-none min-h-[42px] max-h-32 bg-neutral-50 dark:bg-neutral-800 border-neutral-200 dark:border-neutral-700 focus-visible:ring-blue-500"
            />
            <Button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="bg-blue-600 hover:bg-blue-700 text-white shrink-0"
            >
              <Send size={16} />
              <span className="ml-1.5">Send</span>
            </Button>
          </form>
          <p className="text-xs text-neutral-400 dark:text-neutral-600 mt-1.5">
            Enter to send · Shift+Enter for new line
          </p>
        </div>
      </main>
    </>
  )
}
