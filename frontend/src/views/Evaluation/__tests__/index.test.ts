import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { vi } from 'vitest'

import { authApi } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { makeUser } from '@/test/factories'
import EvaluationPage from '../index.vue'


vi.mock('@/api/auth', () => ({
  authApi: {
    getUserInfo: vi.fn()
  }
}))


const renderPage = async (isAdmin: boolean) => {
  const pinia = createPinia()
  setActivePinia(pinia)
  const authStore = useAuthStore()
  authStore.$patch({
    isAuthenticated: true,
    user: makeUser()
  })
  vi.mocked(authApi.getUserInfo).mockResolvedValue({
    success: true,
    data: makeUser(isAdmin),
    message: '获取用户信息成功'
  })

  const wrapper = mount(EvaluationPage, {
    global: { plugins: [pinia] }
  })
  await flushPromises()
  return wrapper
}


describe('Evaluation page access', () => {
  it('shows a read-only Evaluation area to an ordinary signed-in user', async () => {
    const wrapper = await renderPage(false)

    expect(wrapper.text()).toContain('历史回顾评估')
    expect(wrapper.text()).toContain('只读访问')
    expect(wrapper.text()).not.toContain('Evaluation 管理')
  })

  it('shows Evaluation management entry only to an administrator', async () => {
    const wrapper = await renderPage(true)

    expect(wrapper.text()).toContain('历史回顾评估')
    expect(wrapper.text()).toContain('Evaluation 管理')
    expect(wrapper.text()).not.toContain('只读访问')
  })
})
