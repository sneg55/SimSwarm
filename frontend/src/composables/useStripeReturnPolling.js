import { ref, onUnmounted } from 'vue'

// Stripe webhook is async — when the user returns from Checkout the credit
// may not yet be in the ledger. Poll /billing/balance for a window so the
// new balance lands in the UI without forcing a manual refresh.
const DEFAULT_INTERVAL_MS = 3000
const DEFAULT_MAX_DURATION_MS = 30000

export function useStripeReturnPolling({ getBalance, creditsStore, intervalMs = DEFAULT_INTERVAL_MS, maxDurationMs = DEFAULT_MAX_DURATION_MS } = {}) {
  const polling = ref(false)
  let timerId = null
  let stopAt = 0

  function stop() {
    if (timerId !== null) {
      clearTimeout(timerId)
      timerId = null
    }
    polling.value = false
  }

  async function tick(initialBalance) {
    try {
      const data = await getBalance()
      const next = data.balance ?? data
      if (next > initialBalance) {
        creditsStore.setBalance(next)
        stop()
        return
      }
    } catch (err) {
      console.error('Balance poll failed:', err)
    }
    if (Date.now() >= stopAt) {
      stop()
      return
    }
    timerId = setTimeout(() => tick(initialBalance), intervalMs)
  }

  function start(initialBalance) {
    if (polling.value) return
    polling.value = true
    stopAt = Date.now() + maxDurationMs
    timerId = setTimeout(() => tick(initialBalance), intervalMs)
  }

  onUnmounted(stop)

  return { polling, start, stop }
}
