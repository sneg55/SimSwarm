import { ref } from 'vue'

// Module-scoped singletons — shared across all consumers in the app.
let _activeRoundIndex = ref(0)

export function useStoryScrollSync() {
  function setActiveRoundIndex(i) {
    if (typeof i !== 'number' || Number.isNaN(i)) return
    _activeRoundIndex.value = Math.max(0, Math.floor(i))
  }
  return {
    activeRoundIndex: _activeRoundIndex,
    setActiveRoundIndex,
  }
}

// Test helper — do not use in app code.
export function __resetStoryScrollSync() {
  _activeRoundIndex = ref(0)
}
