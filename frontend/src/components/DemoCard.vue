<template>
  <router-link
    :to="`/demo/${slug}`"
    class="block p-6 bg-white border border-gray-200 rounded-lg hover:border-blue-300 hover:shadow-md transition-all"
  >
    <h3 class="font-semibold text-gray-900 mb-2">{{ title }}</h3>
    <p class="text-sm text-gray-500">{{ description }}</p>
    <div class="mt-4 text-sm text-blue-600 font-medium">View demo &rarr;</div>
  </router-link>
</template>

<script setup>
defineProps({
  slug: {
    type: String,
    required: true,
  },
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    default: '',
  },
})
</script>
