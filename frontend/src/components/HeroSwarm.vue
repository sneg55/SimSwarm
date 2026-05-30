<template>
  <div ref="containerRef" class="absolute inset-0 overflow-hidden z-0">
    <canvas ref="canvasRef" class="block w-full h-full" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const containerRef = ref(null)
const canvasRef = ref(null)

const AGENT_COUNT = 120
const MOUSE_RADIUS = 200
const MOUSE_FORCE = 0.035
const FRICTION = 0.98
const CONNECTION_DIST = 80
const HOME_FORCE = 0.00008
const NUM_ATTRACTORS = 5

const palette = [
  { r: 34, g: 211, b: 238 },
  { r: 167, g: 139, b: 250 },
  { r: 110, g: 231, b: 183 },
  { r: 255, g: 107, b: 107 },
  { r: 251, g: 191, b: 36 },
]

let agents = []
let attractors = []
let mouse = { x: -1000, y: -1000 }
let ctx = null
let dpr = 1
let raf = null
let lastTime = 0

function initAgents(w, h) {
  agents = []
  for (let i = 0; i < AGENT_COUNT; i++) {
    const c = palette[Math.floor(Math.random() * palette.length)]
    const hx = Math.random()
    const hy = Math.random()
    agents.push({
      x: hx * w, y: hy * h,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      size: 1.5 + Math.random() * 2.5,
      color: c,
      homeX: hx, homeY: hy,
      phase: Math.random() * Math.PI * 2,
    })
  }
}

function initAttractors() {
  attractors = []
  for (let i = 0; i < NUM_ATTRACTORS; i++) {
    attractors.push({
      x: Math.random(), y: Math.random(),
      vx: (Math.random() - 0.5) * 0.0008,
      vy: (Math.random() - 0.5) * 0.0008,
      strength: 0, targetStrength: 0,
      radius: 120 + Math.random() * 80,
      nextActivate: 3 + Math.random() * 8,
      activeDuration: 0,
      maxDuration: 4 + Math.random() * 6,
    })
  }
}

function resize() {
  if (!containerRef.value || !canvasRef.value) return
  const w = containerRef.value.clientWidth
  const h = containerRef.value.clientHeight
  dpr = window.devicePixelRatio || 1
  canvasRef.value.width = w * dpr
  canvasRef.value.height = h * dpr
  canvasRef.value.style.width = w + 'px'
  canvasRef.value.style.height = h + 'px'
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
}

function animate(timestamp) {
  if (!containerRef.value) return
  const W = containerRef.value.clientWidth
  const H = containerRef.value.clientHeight
  const time = timestamp * 0.001
  const dt = Math.min(time - lastTime, 0.05)
  lastTime = time
  ctx.clearRect(0, 0, W, H)

  // Update attractors
  for (const att of attractors) {
    att.x += att.vx
    att.y += att.vy
    if (att.x < 0.05 || att.x > 0.95) att.vx *= -1
    if (att.y < 0.05 || att.y > 0.95) att.vy *= -1
    att.x = Math.max(0.05, Math.min(0.95, att.x))
    att.y = Math.max(0.05, Math.min(0.95, att.y))

    if (att.targetStrength === 0) {
      att.nextActivate -= dt
      if (att.nextActivate <= 0) {
        att.targetStrength = 0.0015 + Math.random() * 0.001
        att.activeDuration = 0
        att.maxDuration = 4 + Math.random() * 6
        att.vx = (Math.random() - 0.5) * 0.001
        att.vy = (Math.random() - 0.5) * 0.001
      }
    } else {
      att.activeDuration += dt
      if (att.activeDuration >= att.maxDuration) {
        att.targetStrength = 0
        att.nextActivate = 5 + Math.random() * 10
        att.radius = 120 + Math.random() * 80
      }
    }
    att.strength += (att.targetStrength - att.strength) * 0.02
  }

  // Update agents
  for (let i = 0; i < agents.length; i++) {
    const a = agents[i]
    a.vx += (a.homeX * W - a.x) * HOME_FORCE
    a.vy += (a.homeY * H - a.y) * HOME_FORCE
    a.vx += Math.sin(time * 0.4 + a.phase) * 0.012
    a.vy += Math.cos(time * 0.3 + a.phase * 1.7) * 0.012

    for (const att of attractors) {
      if (att.strength < 0.0001) continue
      const ax = att.x * W, ay = att.y * H
      const dx = ax - a.x, dy = ay - a.y
      const d = Math.sqrt(dx * dx + dy * dy)
      if (d < att.radius && d > 15) {
        a.vx += (dx / d) * att.strength * (att.radius - d)
        a.vy += (dy / d) * att.strength * (att.radius - d)
      }
      if (d < att.radius * 0.7 && d > 20) {
        a.vx += (-dy / d) * att.strength * 0.3
        a.vy += (dx / d) * att.strength * 0.3
      }
    }

    for (let j = i + 1; j < agents.length; j++) {
      const b = agents[j]
      const dx = b.x - a.x, dy = b.y - a.y
      const d = Math.sqrt(dx * dx + dy * dy)
      if (d < 20 && d > 1) {
        const rep = 0.004 * (1 - d / 20)
        a.vx -= (dx / d) * rep
        a.vy -= (dy / d) * rep
        b.vx += (dx / d) * rep
        b.vy += (dy / d) * rep
      }
    }

    const mdx = mouse.x - a.x, mdy = mouse.y - a.y
    const mdist = Math.sqrt(mdx * mdx + mdy * mdy)
    if (mdist < MOUSE_RADIUS && mdist > 1) {
      const force = MOUSE_FORCE * (1 - mdist / MOUSE_RADIUS)
      a.vx += (mdx / mdist) * force
      a.vy += (mdy / mdist) * force
    }

    a.vx *= FRICTION
    a.vy *= FRICTION
    a.x += a.vx
    a.y += a.vy

    if (a.x < 10) a.vx += 0.15
    if (a.x > W - 10) a.vx -= 0.15
    if (a.y < 10) a.vy += 0.15
    if (a.y > H - 10) a.vy -= 0.15
  }

  // Draw connections
  ctx.lineWidth = 0.5
  for (let i = 0; i < agents.length; i++) {
    for (let j = i + 1; j < agents.length; j++) {
      const a = agents[i], b = agents[j]
      const dx = a.x - b.x, dy = a.y - b.y
      const d = Math.sqrt(dx * dx + dy * dy)
      if (d < CONNECTION_DIST) {
        const alpha = (1 - d / CONNECTION_DIST) * 0.2
        ctx.beginPath()
        ctx.moveTo(a.x, a.y)
        ctx.lineTo(b.x, b.y)
        ctx.strokeStyle = `rgba(${(a.color.r + b.color.r) >> 1},${(a.color.g + b.color.g) >> 1},${(a.color.b + b.color.b) >> 1},${alpha})`
        ctx.stroke()
      }
    }
  }

  // Draw agents
  for (const a of agents) {
    const pulse = 1 + Math.sin(time * 1.5 + a.phase) * 0.12
    const s = a.size * pulse

    const grad = ctx.createRadialGradient(a.x, a.y, 0, a.x, a.y, s * 6)
    grad.addColorStop(0, `rgba(${a.color.r},${a.color.g},${a.color.b},0.2)`)
    grad.addColorStop(0.4, `rgba(${a.color.r},${a.color.g},${a.color.b},0.05)`)
    grad.addColorStop(1, `rgba(${a.color.r},${a.color.g},${a.color.b},0)`)
    ctx.beginPath()
    ctx.arc(a.x, a.y, s * 6, 0, Math.PI * 2)
    ctx.fillStyle = grad
    ctx.fill()

    ctx.beginPath()
    ctx.arc(a.x, a.y, s, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(${a.color.r},${a.color.g},${a.color.b},0.85)`
    ctx.fill()

    ctx.beginPath()
    ctx.arc(a.x, a.y, s * 0.35, 0, Math.PI * 2)
    ctx.fillStyle = 'rgba(255,255,255,0.3)'
    ctx.fill()
  }

  raf = requestAnimationFrame(animate)
}

function onMouseMove(e) {
  if (!canvasRef.value) return
  const rect = canvasRef.value.getBoundingClientRect()
  mouse.x = e.clientX - rect.left
  mouse.y = e.clientY - rect.top
}

function onMouseLeave() {
  mouse.x = -1000
  mouse.y = -1000
}

onMounted(() => {
  ctx = canvasRef.value.getContext('2d')
  resize()
  const W = containerRef.value.clientWidth
  const H = containerRef.value.clientHeight
  initAttractors()
  initAgents(W, H)
  lastTime = performance.now() * 0.001
  // Skip animation loop for users who prefer reduced motion — render once static
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    ctx.clearRect(0, 0, W, H)
    for (const a of agents) {
      ctx.beginPath()
      ctx.arc(a.x, a.y, a.size, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(${a.color.r},${a.color.g},${a.color.b},0.5)`
      ctx.fill()
    }
    return
  }
  raf = requestAnimationFrame(animate)

  const parent = containerRef.value.parentElement
  parent.addEventListener('mousemove', onMouseMove)
  parent.addEventListener('mouseleave', onMouseLeave)
  window.addEventListener('resize', resize)
})

onUnmounted(() => {
  cancelAnimationFrame(raf)
  const parent = containerRef.value?.parentElement
  if (parent) {
    parent.removeEventListener('mousemove', onMouseMove)
    parent.removeEventListener('mouseleave', onMouseLeave)
  }
  window.removeEventListener('resize', resize)
})
</script>
