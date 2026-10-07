import type { User } from '@/types/auth'


export const makeUser = (isAdmin = false): User => ({
  id: isAdmin ? 'admin-id' : 'viewer-id',
  username: isAdmin ? 'admin' : 'viewer',
  email: isAdmin ? 'admin@example.com' : 'viewer@example.com',
  is_active: true,
  is_verified: true,
  is_admin: isAdmin,
  created_at: '2026-09-06T00:00:00Z',
  updated_at: '2026-09-06T00:00:00Z',
  preferences: {
    default_market: 'A股',
    default_depth: '3',
    ui_theme: 'light',
    language: 'zh-CN',
    notifications_enabled: true,
    email_notifications: false
  },
  daily_quota: 1000,
  concurrent_limit: 3,
  total_analyses: 0,
  successful_analyses: 0,
  failed_analyses: 0
})
