<template>
  <router-link
    :to="`/demo/${slug}`"
    class="block p-6 bg-ocean-deep border border-mist-depth rounded-xl
           transition-all duration-350 ease-spring
           hover:-translate-y-1 hover:border-ocean-teal hover:shadow-[0_8px_32px_rgba(0,0,0,0.3)]"
  >
    <h3 class="font-semibold text-mist-foam mb-2">{{ title }}</h3>
    <p class="text-sm text-mist-drift">{{ description }}</p>
    <div class="mt-4 text-sm text-ocean-glow font-medium">View demo &rarr;</div>
  </router-link>
</template>

<script setup>
defineProps({
  slug: { type: String, required: true },
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
</script>
