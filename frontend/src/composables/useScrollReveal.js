import { onMounted, onBeforeUnmount } from 'vue'

/**
 * Composable that adds scroll-triggered reveal animations.
 * Elements with [data-reveal] start hidden and fade+slide in when visible.
 * Elements with [data-reveal-stagger] children animate in sequence.
 *
 * Usage: call useScrollReveal() in setup(), add data-reveal to elements.
 */
export function useScrollReveal() {
  let observer = null

  onMounted(() => {
    observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('revealed')
            // Stagger children if requested
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
      { threshold: 0.12 }
    )

    // Observe all [data-reveal] elements
    document.querySelectorAll('[data-reveal]').forEach((el) => {
      observer.observe(el)
    })
  })

  onBeforeUnmount(() => {
    if (observer) observer.disconnect()
  })
}
