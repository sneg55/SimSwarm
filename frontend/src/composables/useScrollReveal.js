import { onMounted, onBeforeUnmount, nextTick, watch } from 'vue'

/**
 * Composable that adds scroll-triggered reveal animations.
 * Elements with [data-reveal] start hidden and fade+slide in when visible.
 * Elements with [data-reveal-stagger] children animate in sequence.
 *
 * Automatically re-scans for new [data-reveal] elements when the DOM changes.
 */
export function useScrollReveal() {
  let observer = null
  let mutationObserver = null
  const observed = new WeakSet()

  function scanAndObserve() {
    if (!observer) return
    document.querySelectorAll('[data-reveal]').forEach((el) => {
      if (!observed.has(el)) {
        observed.add(el)
        observer.observe(el)
      }
    })
  }

  onMounted(() => {
    observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('revealed')
            if (entry.target.hasAttribute('data-reveal-stagger')) {
              const children = entry.target.querySelectorAll('[data-reveal-child]')
              children.forEach((child, i) => {
                child.style.transitionDelay = `${i * 120}ms`
                child.classList.add('revealed')
              })
            }
            observer.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.05, rootMargin: '0px 0px 50px 0px' }
    )

    // Initial scan after Vue renders
    nextTick(() => scanAndObserve())

    // Re-scan when DOM changes (handles v-if content appearing after async load)
    mutationObserver = new MutationObserver(() => scanAndObserve())
    mutationObserver.observe(document.body, { childList: true, subtree: true })
  })

  onBeforeUnmount(() => {
    if (observer) observer.disconnect()
    if (mutationObserver) mutationObserver.disconnect()
  })
}
