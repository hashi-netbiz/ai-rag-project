'use client'

import { motion } from 'motion/react'

export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-4 py-3 bg-neutral-100 dark:bg-neutral-800 rounded-2xl rounded-bl-sm w-fit">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="block w-2 h-2 rounded-full bg-neutral-400 dark:bg-neutral-500"
          animate={{ y: [0, -6, 0] }}
          transition={{
            duration: 0.6,
            repeat: Infinity,
            delay: i * 0.15,
            ease: 'easeInOut',
          }}
        />
      ))}
    </div>
  )
}
