import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia } from 'pinia'

// Stub child components so pdfjs (and other heavy deps) never load.
vi.mock('../../components/wizard/WizardSeed.vue', () => ({ default: { template: '<div />' } }))
vi.mock('../../components/wizard/WizardGoal.vue', () => ({ default: { template: '<div />' } }))
vi.mock('../../components/wizard/WizardLaunch.vue', () => ({ default: { template: '<div />' } }))
vi.mock('../../components/wizard/WizardProgress.vue', () => ({ default: { template: '<div />' } }))

// The view imports createJob/getBalance etc. Stub them so the component mounts.
vi.mock('../../api/jobs.js', () => ({
  createJob: vi.fn(), createDraft: vi.fn(), updateDraft: vi.fn(),
  launchDraft: vi.fn(), getJob: vi.fn(),
}))
vi.mock('../../api/billing.js', () => ({ getBalance: vi.fn().mockResolvedValue({ balance: 100 }) }))

async function mountView() {
  const NewSimulation = (await import('../NewSimulation.vue')).default
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: NewSimulation }],
  })
  router.push('/')
  await router.isReady()
  return mount(NewSimulation, { global: { plugins: [router, createPinia()] } })
}

describe('NewSimulation step 1 — enrichWeb toggle surface', () => {
  it('description paragraph is NOT a descendant of the <label>', async () => {
    const wrapper = await mountView()
    const label = wrapper.find('label')
    expect(label.exists()).toBe(true)
    // The description <p> must NOT be inside the <label> — if it is, browser
    // clicks on the text accidentally toggle the checkbox.
    const descInsideLabel = label.find('p.text-xs.text-mist-slate')
    expect(descInsideLabel.exists()).toBe(false)
  })

  it('description paragraph exists outside the <label>', async () => {
    const wrapper = await mountView()
    // Default is true (see script setup: const enrichWeb = ref(true)).
    expect(wrapper.vm.enrichWeb).toBe(true)
    const desc = wrapper.find('p.text-xs.text-mist-slate')
    expect(desc.exists()).toBe(true)
  })

  it('clicking the title span toggles enrichWeb', async () => {
    const wrapper = await mountView()
    const initial = wrapper.vm.enrichWeb
    // Use setValue to simulate a user toggling the checkbox (v-model + jsdom).
    const checkbox = wrapper.find('input[type="checkbox"]')
    expect(checkbox.exists()).toBe(true)
    await checkbox.setValue(!initial)
    expect(wrapper.vm.enrichWeb).toBe(!initial)
  })
})
