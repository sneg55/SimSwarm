import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getConfig } from '../api/config.js'

const STATIC = import.meta.env.VITE_STATIC_DEMO === 'true'

export const useConfigStore = defineStore('config', () => {
  const demoMode = ref(false)
  const loaded = ref(false)

  async function load() {
    if (STATIC) {
      demoMode.value = true   // static snapshot is always a read-only demo
      loaded.value = true
      return
    }
    try {
      const cfg = await getConfig()
      demoMode.value = !!cfg.demo_mode
    } catch (e) {
      demoMode.value = false   // fail open to full-platform UX
    } finally {
      loaded.value = true
    }
  }

  return { demoMode, loaded, load }
})
