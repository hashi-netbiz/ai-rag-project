import { NextRequest, NextResponse } from 'next/server'
import { FASTAPI_BASE_URL } from '@/lib/constants'

export async function GET(req: NextRequest): Promise<NextResponse> {
  const authHeader = req.headers.get('Authorization') ?? ''

  const upstream = await fetch(`${FASTAPI_BASE_URL}/auth/me`, {
    headers: { Authorization: authHeader },
  })

  const data: unknown = await upstream.json()
  return NextResponse.json(data, { status: upstream.status })
}
