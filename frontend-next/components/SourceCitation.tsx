'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp, FileText } from 'lucide-react'
import { motion, AnimatePresence } from 'motion/react'
import type { Source } from '@/types/api'

interface SourceCitationProps {
  sources: Source[]
}

export function SourceCitation({ sources }: SourceCitationProps) {
  const [open, setOpen] = useState(false)

  if (sources.length === 0) return null

  return (
    <div className="mt-3 border-t border-neutral-200 dark:border-neutral-700 pt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs text-neutral-500 dark:text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 transition-colors"
        aria-expanded={open}
        type="button"
      >
        {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        {sources.length} source{sources.length > 1 ? 's' : ''}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="flex flex-wrap gap-1.5 mt-2">
              {sources.map((source, i) => {
                const label = source.section
                  ? `${source.file} › ${source.section}`
                  : source.file
                return (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300 rounded-full px-2.5 py-0.5 text-xs"
                  >
                    <FileText size={10} />
                    {label}
                  </span>
                )
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
