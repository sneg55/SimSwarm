<template>
  <div>
    <!-- Hero Section -->
    <section class="bg-gradient-to-br from-blue-600 to-blue-800 text-white py-20">
      <div class="max-w-4xl mx-auto px-4 text-center">
        <h1 class="text-5xl font-bold mb-6">AI-Powered Market Simulations</h1>
        <p class="text-xl text-blue-100 mb-8">
          Run deep research simulations powered by multi-agent AI. Analyze markets, strategies, and opportunities at scale.
        </p>
        <div class="flex items-center justify-center gap-4">
          <router-link
            to="/register"
            class="px-8 py-3 bg-white text-blue-600 font-semibold rounded-lg hover:bg-blue-50 transition-colors"
          >
            Start for free
          </router-link>
          <router-link
            to="/demo/fish-market"
            class="px-8 py-3 border border-white text-white font-semibold rounded-lg hover:bg-white/10 transition-colors"
          >
            View Demo
          </router-link>
        </div>
      </div>
    </section>

    <!-- Demo Links Section -->
    <section class="py-16 bg-gray-50">
      <div class="max-w-4xl mx-auto px-4">
        <h2 class="text-3xl font-bold text-center text-gray-900 mb-8">See It In Action</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <router-link
            v-for="demo in demos"
            :key="demo.slug"
            :to="`/demo/${demo.slug}`"
            class="block p-6 bg-white border border-gray-200 rounded-lg hover:border-blue-300 hover:shadow-md transition-all"
          >
            <div class="text-2xl mb-2">{{ demo.icon }}</div>
            <h3 class="font-semibold text-gray-900 mb-1">{{ demo.title }}</h3>
            <p class="text-sm text-gray-500">{{ demo.description }}</p>
          </router-link>
        </div>
      </div>
    </section>

    <!-- Pricing Section -->
    <section class="py-16">
      <div class="max-w-4xl mx-auto px-4">
        <h2 class="text-3xl font-bold text-center text-gray-900 mb-4">Simple Credit Pricing</h2>
        <p class="text-center text-gray-500 mb-10">Pay only for what you use. No subscriptions.</p>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div v-for="tier in pricingTiers" :key="tier.name" class="border rounded-lg p-6 text-center">
            <h3 class="text-xl font-bold text-gray-900 mb-1">{{ tier.name }}</h3>
            <div class="text-3xl font-bold text-blue-600 my-4">{{ tier.credits }}<span class="text-sm text-gray-500 font-normal"> credits</span></div>
            <p class="text-sm text-gray-500 mb-4">{{ tier.description }}</p>
            <p class="font-semibold text-gray-800">{{ tier.price }}</p>
          </div>
        </div>
        <div class="text-center mt-8">
          <router-link
            to="/register"
            class="px-8 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors"
          >
            Get started free
          </router-link>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
const demos = [
  { slug: 'fish-market', icon: '🐟', title: 'Fish Market Analysis', description: 'Deep dive into global seafood market trends.' },
  { slug: 'competitor-map', icon: '📊', title: 'Competitor Mapping', description: 'Analyze competitive landscape automatically.' },
  { slug: 'supply-chain', icon: '🔗', title: 'Supply Chain Risk', description: 'Identify and quantify supply chain vulnerabilities.' },
]

const pricingTiers = [
  { name: 'Starter', credits: 100, price: '$9', description: 'Perfect for small projects' },
  { name: 'Growth', credits: 500, price: '$39', description: 'For teams and regular use' },
  { name: 'Scale', credits: 2000, price: '$129', description: 'For enterprise workflows' },
]
</script>
