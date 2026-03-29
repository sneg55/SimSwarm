<template>
  <div class="text-center py-16">
    <div class="relative w-48 h-48 mx-auto mb-10">
      <!-- Orbital rings -->
      <div class="orbital-ring ring-1" />
      <div class="orbital-ring ring-2" />
      <div class="orbital-ring ring-3" />

      <!-- Orbiting dot 1 — cyan, fast -->
      <div class="orbit-path orbit-1">
        <div class="dot dot-cyan" />
      </div>

      <!-- Orbiting dot 2 — violet, medium, reverse -->
      <div class="orbit-path orbit-2">
        <div class="dot dot-violet" />
      </div>

      <!-- Orbiting dot 3 — coral, slow -->
      <div class="orbit-path orbit-3">
        <div class="dot dot-coral" />
      </div>

      <!-- Sweeping arc — orbits independently -->
      <div class="orbit-path orbit-arc">
        <svg class="arc-svg" width="48" height="48" viewBox="0 0 48 48">
          <path
            d="M 8 4 A 40 40 0 0 1 44 24"
            fill="none"
            stroke="url(#arcGrad)"
            stroke-width="2.5"
            stroke-linecap="round"
          />
          <defs>
            <linearGradient id="arcGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="rgba(255,107,107,0)" />
              <stop offset="40%" stop-color="rgba(255,107,107,0.8)" />
              <stop offset="100%" stop-color="rgba(255,107,107,0)" />
            </linearGradient>
          </defs>
        </svg>
      </div>

      <!-- Center nucleus -->
      <div class="nucleus">
        <div class="nucleus-glow" />
        <div class="nucleus-core" />
        <div class="nucleus-dot" />
      </div>
    </div>

    <p class="text-lg text-mist-drift max-w-sm mx-auto mb-6 leading-relaxed">
      Your ecosystem is ready.<br>What would you like to simulate today?
    </p>

    <router-link
      to="/sim/new"
      class="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-base font-semibold text-white
             bg-gradient-to-br from-ocean-cyan to-cyan-500
             glow-cyan transition-all duration-250 ease-spring
             hover:glow-cyan-lg hover:-translate-y-0.5"
    >
      Start your first simulation
    </router-link>
  </div>
</template>

<script setup>
</script>

<style scoped>
/* Orbital rings — concentric, pulsing */
.orbital-ring {
  position: absolute;
  border-radius: 50%;
  border: 1px solid;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
}
.ring-1 {
  width: 80px; height: 80px;
  border-color: rgba(34,211,238,0.15);
  animation: pulse-ring 4s ease-in-out infinite;
}
.ring-2 {
  width: 120px; height: 120px;
  border-color: rgba(167,139,250,0.1);
  animation: pulse-ring 4s ease-in-out infinite 1.3s;
}
.ring-3 {
  width: 160px; height: 160px;
  border-color: rgba(255,107,107,0.08);
  animation: pulse-ring 4s ease-in-out infinite 2.6s;
}

@keyframes pulse-ring {
  0%, 100% { transform: translate(-50%,-50%) scale(1); opacity: 1; }
  50% { transform: translate(-50%,-50%) scale(1.06); opacity: 0.4; }
}

/* Orbit paths — rotating containers that carry the dots */
.orbit-path {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  animation: orbit linear infinite;
}
.orbit-1 { animation-duration: 8s; }
.orbit-2 { animation-duration: 13s; animation-direction: reverse; animation-delay: -3s; }
.orbit-3 { animation-duration: 18s; animation-delay: -7s; }
.orbit-arc { animation-duration: 10s; animation-delay: -2s; }

@keyframes orbit {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Dots positioned on the orbit edge */
.dot {
  position: absolute;
  border-radius: 50%;
  animation: glow-breathe 3s ease-in-out infinite;
}
.dot-cyan {
  width: 10px; height: 10px;
  background: #22d3ee;
  box-shadow: 0 0 12px 3px rgba(34,211,238,0.5);
  top: 14px; left: 50%; transform: translateX(-50%);
}
.dot-violet {
  width: 8px; height: 8px;
  background: #a78bfa;
  box-shadow: 0 0 10px 2px rgba(167,139,250,0.4);
  bottom: 22px; right: 16px;
  animation-delay: 1s;
}
.dot-coral {
  width: 8px; height: 8px;
  background: #ff6b6b;
  box-shadow: 0 0 10px 2px rgba(255,107,107,0.4);
  bottom: 28px; left: 16px;
  animation-delay: 2s;
}

@keyframes glow-breathe {
  0%, 100% { opacity: 0.7; transform: translateX(-50%) scale(1); }
  50% { opacity: 1; transform: translateX(-50%) scale(1.3); }
}
.dot-violet, .dot-coral {
  animation-name: glow-breathe-alt;
}
@keyframes glow-breathe-alt {
  0%, 100% { opacity: 0.6; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.3); }
}

/* Arc SVG — positioned at edge of orbit */
.arc-svg {
  position: absolute;
  top: -4px; right: -4px;
}

/* Center nucleus */
.nucleus {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
}
.nucleus-glow {
  position: absolute;
  width: 32px; height: 32px;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: radial-gradient(circle, rgba(34,211,238,0.3) 0%, transparent 70%);
  animation: nucleus-pulse 3s ease-in-out infinite;
}
.nucleus-core {
  position: absolute;
  width: 20px; height: 20px;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: rgba(34,211,238,0.8);
  box-shadow: 0 0 20px 6px rgba(34,211,238,0.3);
  animation: nucleus-pulse 3s ease-in-out infinite;
}
.nucleus-dot {
  position: absolute;
  width: 8px; height: 8px;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: #e0f7fa;
}

@keyframes nucleus-pulse {
  0%, 100% { transform: translate(-50%,-50%) scale(1); opacity: 0.8; }
  50% { transform: translate(-50%,-50%) scale(1.15); opacity: 1; }
}
</style>
