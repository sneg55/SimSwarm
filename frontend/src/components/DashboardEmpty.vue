<template>
  <div class="text-center py-20">
    <div class="relative w-28 h-28 mx-auto mb-8">
      <!-- Pulsing rings -->
      <div
        v-for="(ring, i) in rings" :key="i"
        class="absolute inset-0 rounded-full border"
        :style="{
          borderColor: ring.color,
          animation: 'pulse-ring 4s ease-in-out infinite',
          animationDelay: ring.delay,
        }"
      />

      <!-- Orbiting dots -->
      <div class="absolute inset-0 animate-orbit" style="animation-duration: 12s;">
        <div class="absolute w-2.5 h-2.5 rounded-full bg-ocean-glow top-0 left-1/2 -translate-x-1/2 animate-glow-breathe" />
      </div>
      <div class="absolute inset-0 animate-orbit" style="animation-duration: 18s; animation-delay: -4s; animation-direction: reverse;">
        <div class="absolute w-2 h-2 rounded-full bg-organic-violet bottom-0 right-0 animate-glow-breathe" style="animation-delay: 1s;" />
      </div>
      <div class="absolute inset-0 animate-orbit" style="animation-duration: 15s; animation-delay: -8s;">
        <div class="absolute w-2 h-2 rounded-full bg-coral bottom-2 left-0 animate-glow-breathe" style="animation-delay: 2s;" />
      </div>

      <!-- Sweeping arc -->
      <svg class="absolute inset-0 w-full h-full animate-orbit" style="animation-duration: 10s;" viewBox="0 0 112 112">
        <path
          d="M 90 20 A 50 50 0 0 1 98 56"
          fill="none"
          stroke="url(#arcGradient)"
          stroke-width="2.5"
          stroke-linecap="round"
        />
        <defs>
          <linearGradient id="arcGradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="rgba(255,107,107,0)" />
            <stop offset="50%" stop-color="rgba(255,107,107,0.7)" />
            <stop offset="100%" stop-color="rgba(255,107,107,0)" />
          </linearGradient>
        </defs>
      </svg>

      <!-- Center nucleus -->
      <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-ocean-cyan/80 animate-nucleus-pulse" />
      <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-mist-foam/80" />
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
const rings = [
  { color: 'rgba(34, 211, 238, 0.15)', delay: '0s' },
  { color: 'rgba(167, 139, 250, 0.12)', delay: '1.3s' },
  { color: 'rgba(255, 107, 107, 0.1)', delay: '2.6s' },
]
</script>

<style scoped>
@keyframes pulse-ring {
  0%, 100% { transform: scale(0.85); opacity: 0.15; }
  50% { transform: scale(1.15); opacity: 0.04; }
}

@keyframes orbit {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes nucleus-pulse {
  0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.8; }
  50% { transform: translate(-50%, -50%) scale(1.15); opacity: 1; }
}

.animate-orbit {
  animation: orbit 12s linear infinite;
}

.animate-nucleus-pulse {
  animation: nucleus-pulse 3s ease-in-out infinite;
}
</style>
