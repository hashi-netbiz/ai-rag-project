export const FASTAPI_BASE_URL = process.env.FASTAPI_BASE_URL ?? 'http://localhost:8000'

export const ROLE_COLORS: Record<string, string> = {
  finance: 'bg-green-600',
  marketing: 'bg-purple-600',
  hr: 'bg-orange-500',
  engineering: 'bg-blue-600',
  c_level: 'bg-yellow-500',
  employee: 'bg-neutral-500',
}

export const ROLE_LABELS: Record<string, string> = {
  finance: 'Finance',
  marketing: 'Marketing',
  hr: 'HR',
  engineering: 'Engineering',
  c_level: 'C-Level',
  employee: 'Employee',
}

export const ROLE_SUGGESTIONS: Record<string, string[]> = {
  finance: [
    'What is our current gross margin?',
    'Summarize the quarterly financial report.',
    'What were the key budget variances this quarter?',
  ],
  marketing: [
    'What were the results of the latest campaign?',
    'Summarize our brand positioning strategy.',
    'What is our target customer segment?',
  ],
  hr: [
    'What is the current headcount by department?',
    'Summarize the employee handbook leave policies.',
    'What is our referral bonus policy?',
  ],
  engineering: [
    'Describe the high-level system architecture.',
    'What databases are used in the data layer?',
    'What is the authentication standard?',
  ],
  c_level: [
    'Give me an executive summary of company performance.',
    'What are the top financial metrics this quarter?',
    'Summarize headcount and department breakdown.',
  ],
  employee: [
    'What is the annual leave entitlement?',
    'What is the work-from-home policy?',
    'When is salary credited each month?',
  ],
}
