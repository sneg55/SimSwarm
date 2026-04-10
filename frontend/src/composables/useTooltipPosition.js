import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'

const VIEWPORT_MARGIN = 8

const OPPOSITE = { top: 'bottom', bottom: 'top', left: 'right', right: 'left' }

export const reducedMotion =
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

function calcPosition(pos, triggerRect, panelRect) {
  if (pos === 'top') {
    return {
      top: triggerRect.top - panelRect.height - 8,
      left: triggerRect.left + triggerRect.width / 2 - panelRect.width / 2,
    }
  }
  if (pos === 'bottom') {
    return {
      top: triggerRect.bottom + 8,
      left: triggerRect.left + triggerRect.width / 2 - panelRect.width / 2,
    }
  }
  if (pos === 'left') {
    return {
      top: triggerRect.top + triggerRect.height / 2 - panelRect.height / 2,
      left: triggerRect.left - panelRect.width - 8,
    }
  }
  // right
  return {
    top: triggerRect.top + triggerRect.height / 2 - panelRect.height / 2,
    left: triggerRect.right + 8,
  }
}

function clips(p, rect) {
  const vw = window.innerWidth
  const vh = window.innerHeight
  return (
    p.top < VIEWPORT_MARGIN ||
    p.left < VIEWPORT_MARGIN ||
    p.top + rect.height > vh - VIEWPORT_MARGIN ||
    p.left + rect.width > vw - VIEWPORT_MARGIN
  )
}

function clamp(val, min, max) {
  return Math.max(min, Math.min(val, max))
}

/**
 * Composable for tooltip visibility, positioning, and keyboard/click-outside handling.
 * @param {import('vue').Ref<boolean>} hasTooltip - whether the tooltip entry exists
 * @param {string} preferredPosition - 'top' | 'bottom' | 'left' | 'right'
 * @param {import('vue').Ref<HTMLElement|null>} triggerRef - ref to the trigger element
 */
export function useTooltipPosition(hasTooltip, preferredPosition, triggerRef) {
  const visible = ref(false)
  const panelRef = ref(null)
  const panelPos = ref({ top: 0, left: 0 })
  const actualPosition = ref(preferredPosition)

  let showTimer = null
  let hideTimer = null

  function clearTimers() {
    if (showTimer) { clearTimeout(showTimer); showTimer = null }
    if (hideTimer) { clearTimeout(hideTimer); hideTimer = null }
  }

  function positionPanel() {
    const panel = panelRef.value
    if (!panel) return
    const trigger = triggerRef?.value
    if (!trigger) return

    const triggerRect = trigger.getBoundingClientRect()
    const panelRect = panel.getBoundingClientRect()
    const vw = window.innerWidth
    const vh = window.innerHeight

    let pos = calcPosition(preferredPosition, triggerRect, panelRect)
    actualPosition.value = preferredPosition

    if (clips(pos, panelRect)) {
      const flipped = calcPosition(OPPOSITE[preferredPosition], triggerRect, panelRect)
      if (!clips(flipped, panelRect)) {
        pos = flipped
        actualPosition.value = OPPOSITE[preferredPosition]
      }
    }

    panelPos.value = {
      top: clamp(pos.top, VIEWPORT_MARGIN, vh - panelRect.height - VIEWPORT_MARGIN),
      left: clamp(pos.left, VIEWPORT_MARGIN, vw - panelRect.width - VIEWPORT_MARGIN),
    }
  }

  function show() {
    clearTimers()
    showTimer = setTimeout(() => {
      visible.value = true
      nextTick(positionPanel)
    }, 200)
  }

  function hide() {
    clearTimers()
    hideTimer = setTimeout(() => { visible.value = false }, 150)
  }

  function onTriggerEnter() { if (hasTooltip.value) show() }
  function onTriggerLeave() { hide() }
  function onPanelEnter() { clearTimers() }
  function onPanelLeave() { hide() }

  function toggleTooltip() {
    if (visible.value) {
      visible.value = false
      clearTimers()
    } else {
      visible.value = true
      nextTick(positionPanel)
    }
  }

  function onEscape(e) {
    if (e.key === 'Escape' && visible.value) {
      visible.value = false
      clearTimers()
    }
  }

  function onClickOutside(e) {
    if (!visible.value) return
    if (panelRef.value?.contains(e.target)) return
    visible.value = false
    clearTimers()
  }

  watch(visible, (val) => {
    if (val) document.addEventListener('click', onClickOutside, true)
    else document.removeEventListener('click', onClickOutside, true)
  })

  onMounted(() => { document.addEventListener('keydown', onEscape) })
  onBeforeUnmount(() => {
    clearTimers()
    document.removeEventListener('keydown', onEscape)
    document.removeEventListener('click', onClickOutside, true)
  })

  return {
    visible, panelRef, panelPos, actualPosition,
    onTriggerEnter, onTriggerLeave, onPanelEnter, onPanelLeave,
    toggleTooltip,
  }
}

/** Vue Transition hooks: opacity + translateY animation */
export function tooltipTransitionHooks() {
  return {
    onBeforeEnter(el) {
      if (reducedMotion) return
      el.style.opacity = '0'
      el.style.transform = 'translateY(4px)'
    },
    onEnter(el, done) {
      if (reducedMotion) { done(); return }
      void el.offsetHeight
      el.style.transition = 'opacity 150ms ease-out, transform 150ms ease-out'
      el.style.opacity = '1'
      el.style.transform = 'translateY(0)'
      setTimeout(done, 150)
    },
    onLeave(el, done) {
      if (reducedMotion) { done(); return }
      el.style.transition = 'opacity 150ms ease-out, transform 150ms ease-out'
      el.style.opacity = '0'
      el.style.transform = 'translateY(4px)'
      setTimeout(done, 150)
    },
  }
}
