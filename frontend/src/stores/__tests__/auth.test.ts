import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { authApi } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { makeUser } from '@/test/factories'


vi.mock('@/api/auth', () => ({
  authApi: {
    login: vi.fn(),
    getUserInfo: vi.fn()
  }
}))

vi.mock('@/utils/auth', () => ({
  setupTokenRefreshTimer: vi.fn()
}))


const viewer = makeUser()


describe('authentication roles', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('keeps an ordinary database user out of the administrator role', async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      success: true,
      data: {
        access_token: 'header.payload.signature',
        refresh_token: 'refresh.payload.signature',
        token_type: 'bearer',
        expires_in: 3600,
        user: viewer
      },
      message: '登录成功'
    })
    const authStore = useAuthStore()

    const loggedIn = await authStore.login({ username: 'viewer', password: 'secret' })

    expect(loggedIn).toBe(true)
    expect(authStore.isAdmin).toBe(false)
    expect(authStore.roles).toEqual(['user'])
    expect(authStore.permissions).toEqual([])
  })

  it('applies the latest backend user role after an administrator is demoted', async () => {
    vi.mocked(authApi.getUserInfo).mockResolvedValue({
      success: true,
      data: viewer,
      message: '获取用户信息成功'
    })
    const authStore = useAuthStore()
    authStore.$patch({
      user: { ...viewer, is_admin: true },
      roles: ['admin'],
      permissions: ['*']
    })

    await authStore.fetchUserInfo()

    expect(authStore.isAdmin).toBe(false)
    expect(authStore.roles).toEqual(['user'])
    expect(authStore.permissions).toEqual([])
  })
})
