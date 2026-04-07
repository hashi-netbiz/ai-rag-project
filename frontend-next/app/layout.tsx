import type { Metadata } from 'next'
import { GeistSans } from 'geist/font/sans'
import { GeistMono } from 'geist/font/mono'
import './globals.css'

export const metadata: Metadata = {
  title: 'Company Assistant',
  description: 'Role-based intranet knowledge assistant',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${GeistSans.variable} ${GeistMono.variable} font-sans antialiased text-foreground bg-black bg-[url('/couple.jpg')] bg-contain bg-no-repeat bg-center`}
        suppressHydrationWarning
      >
        {children}
      </body>
    </html>
  )
}
