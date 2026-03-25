import { NextRequest, NextResponse } from 'next/server'
import { FASTAPI_BASE_URL } from '@/lib/constants'

export async function POST(req: NextRequest): Promise<NextResponse> {
  const body: unknown = await req.json()

  const upstream = await fetch(`${FASTAPI_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  const data: unknown = await upstream.json()
  return NextResponse.json(data, { status: upstream.status })
}
