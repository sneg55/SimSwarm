<template>
  <div
    class="relative overflow-hidden rounded-2xl border p-9 text-center transition-all duration-350 ease-spring hover:-translate-y-1.5 hover:shadow-[0_12px_40px_rgba(0,0,0,0.3)]"
    :class="[
      featured
        ? 'border-ocean-teal bg-gradient-to-b from-ocean-deep to-ocean-abyss shadow-[0_0_40px_rgba(14,116,144,0.1)]'
        : 'border-mist-depth bg-ocean-deep hover:border-ocean-teal',
    ]"
  >
    <div
      class="absolute top-0 left-0 right-0 h-[3px] transition-opacity duration-300"
      :class="featured ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'"
      :style="{ background: accentColor }"
    />

    <div v-if="featured" class="absolute top-4 right-4 text-[11px] font-semibold uppercase tracking-wider text-ocean-glow bg-ocean-glow/10 border border-ocean-glow/20 px-2.5 py-1 rounded-full">
      Most popular
    </div>

    <div class="text-lg font-bold text-mist-foam mb-1">{{ name }}</div>
    <div class="font-mono text-sm text-mist-slate mb-5">{{ credits }} credits</div>
    <div class="text-5xl font-extrabold tracking-tight mb-1 transition-transform duration-300 hover:scale-105" :style="{ color: accentColor }">
      {{ price }}
    </div>
    <div class="text-sm text-mist-slate mb-6">one-time</div>

    <ul class="text-left mb-7 space-y-1.5">
      <li v-for="feature in features" :key="feature" class="flex items-center gap-2 text-sm text-mist-drift">
        <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :style="{ background: accentColor, boxShadow: `0 0 6px ${accentColor}` }" />
        {{ feature }}
      </li>
    </ul>

    <button
      class="w-full py-3 rounded-xl text-[15px] font-semibold transition-all duration-250 ease-spring"
      :class="featured
        ? 'bg-gradient-to-br from-ocean-cyan to-cyan-500 text-white glow-cyan hover:glow-cyan-lg hover:-translate-y-0.5'
        : 'bg-transparent text-mist-drift border border-mist-depth hover:border-ocean-teal hover:text-mist-foam hover:bg-ocean-teal/20 hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(0,0,0,0.2)]'"
    >
      Get started
    </button>
  </div>
</template>

<script setup>
defineProps({
  name: { type: String, required: true },
  credits: { type: Number, required: true },
  price: { type: String, required: true },
  features: { type: Array, required: true },
  accentColor: { type: String, default: '#22D3EE' },
  featured: { type: Boolean, default: false },
})
</script>
