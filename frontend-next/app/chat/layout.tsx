import type { ReactNode } from 'react'

export default function ChatLayout({ children }: { children: ReactNode }) {
  return <div className="h-screen flex overflow-hidden">{children}</div>
}
