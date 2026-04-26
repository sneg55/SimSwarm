<template>
  <div>
    <ScrollProgress />

    <!-- Hero -->
    <section class="relative min-h-screen flex flex-col justify-center items-center text-center pt-20">
      <div class="absolute inset-0 pointer-events-none"
        style="background: radial-gradient(ellipse 80% 60% at 50% 40%, rgba(14,116,144,0.12), transparent), radial-gradient(ellipse 60% 50% at 20% 80%, rgba(167,139,250,0.06), transparent), radial-gradient(ellipse 50% 40% at 80% 70%, rgba(255,107,107,0.04), transparent)"
      />

      <HeroSwarm />

      <h1 class="relative z-10 text-[clamp(36px,5vw,64px)] font-extrabold text-mist-foam tracking-[-0.03em] leading-[1.08] max-w-[720px]">
        What if you could watch<br>
        <HeroRotatingText /><br>
        form in real time?
      </h1>

      <p class="relative z-10 text-[clamp(16px,2vw,20px)] text-mist-drift max-w-[540px] mt-5 leading-relaxed">
        Upload a document. Launch a swarm of AI agents. Watch emergent intelligence reveal how markets, media, and people will react — before it happens.
      </p>

      <p class="relative z-10 text-sm text-mist-slate mt-3">Move your mouse to attract the swarm</p>

      <div class="relative z-10 flex gap-4 mt-10">
        <router-link
          to="/register"
          class="px-8 py-3.5 rounded-xl text-base font-bold text-white
                 bg-gradient-to-br from-coral to-coral-amber
                 glow-coral transition-all duration-250 ease-spring
                 hover:glow-coral-lg hover:-translate-y-0.5"
        >
          Get started
        </router-link>
        <a
          href="#experience"
          class="px-8 py-3.5 rounded-xl text-base font-semibold text-mist
                 border border-mist-depth/60
                 transition-all duration-300
                 hover:border-mist-slate hover:bg-mist-depth/40 hover:text-mist-foam"
        >
          See it in action &#x2193;
        </a>
      </div>

      <div class="relative z-10 flex gap-8 mt-12 text-sm text-mist-slate">
        <span class="flex items-center gap-1.5">&#x1F4B3; Pay-as-you-go credits</span>
        <span class="flex items-center gap-1.5">&#x26A1; Results in minutes, not months</span>
        <span class="flex items-center gap-1.5">&#x1F30A; Up to 1-year forecast horizons</span>
      </div>
    </section>

    <div class="max-w-[1100px] mx-auto h-px bg-gradient-to-r from-transparent via-mist-depth to-transparent" />

    <!-- Experience -->
    <section id="experience" class="px-4 md:px-8">
      <div class="text-center pt-24 pb-16 max-w-[1100px] mx-auto">
        <div class="text-[11px] font-bold uppercase tracking-[0.12em] text-ocean-cyan mb-3">How it works</div>
        <h2 class="text-[clamp(28px,3.5vw,40px)] font-extrabold text-mist-foam tracking-tight">
          Three steps. One living ecosystem.
        </h2>
        <p class="text-[17px] text-mist-drift mt-3 max-w-[540px] mx-auto">
          Drop your document, set your question, and let the swarm reveal what happens next.
        </p>
      </div>

      <ExperienceStep stepNumber="01 — Seed the ecosystem">
        <template #title>Drop your document</template>
        <template #description>
          Upload a press release, policy draft, earnings report, or campaign brief.
          The swarm reads it, extracts entities, and builds a living knowledge graph
          of every stakeholder, market force, and narrative thread.
        </template>
        <template #detail>Supports PDF, DOCX, TXT, Markdown — up to 20,000 characters.</template>
        <template #mockup>
          <div class="border-2 border-dashed border-ocean-teal rounded-xl p-8 text-center transition-colors hover:border-ocean-cyan">
            <div class="text-4xl mb-2 animate-[float_4s_ease-in-out_infinite]">&#x1F30A;</div>
            <div class="text-[15px] text-mist-drift font-medium">Drop your document here</div>
            <div class="text-sm text-mist-slate mt-1.5">or click to browse</div>
            <div class="flex gap-2 justify-center mt-4">
              <span v-for="t in ['Press release', 'Policy draft', 'Report']" :key="t"
                class="text-[11px] text-mist-slate bg-ocean-abyss px-2.5 py-1 rounded-md border border-mist-depth">
                {{ t }}
              </span>
            </div>
          </div>
        </template>
      </ExperienceStep>

      <ExperienceStep stepNumber="02 — Watch the swarm evolve" :reverse="true">
        <template #title>Agents school and interact</template>
        <template #description>
          Hundreds of AI agents — each representing a market participant, journalist,
          regulator, or public voice — begin to interact. Watch opinion clusters form,
          alliances shift, and consensus emerge like a living ecosystem.
        </template>
        <template #detail>Real-time progress with agent chat replay.</template>
        <template #mockup>
          <div class="relative h-[220px] overflow-hidden">
            <div
              v-for="i in 24" :key="i"
              class="absolute rounded-full"
              :style="agentStyle(i)"
            />
          </div>
        </template>
      </ExperienceStep>

      <ExperienceStep stepNumber="03 — Insights surface naturally">
        <template #title>The ecosystem reveals patterns</template>
        <template #description>
          The swarm's emergent intelligence distills into a clear, scrollable narrative —
          key findings, sentiment shifts, coalition maps, and confidence scores.
          No PhD required. Just scroll and understand.
        </template>
        <template #detail>Export as PDF or CSV for your team.</template>
        <template #mockup>
          <div
            v-for="insight in insights" :key="insight.label"
            class="bg-ocean-abyss border border-mist-depth rounded-lg p-4 mb-2.5 transition-transform duration-300 hover:translate-x-1"
            :style="{ borderLeftWidth: '3px', borderLeftColor: insight.color }"
          >
            <div class="text-[11px] font-semibold uppercase tracking-wider mb-1.5" :style="{ color: insight.color }">
              {{ insight.label }}
            </div>
            <div class="text-sm text-mist" :class="insight.mono ? 'font-mono text-mist-drift text-[13px]' : ''">
              {{ insight.text }}
            </div>
          </div>
        </template>
      </ExperienceStep>
    </section>

    <div class="max-w-[1100px] mx-auto h-px bg-gradient-to-r from-transparent via-mist-depth to-transparent" />

    <!-- Demos -->
    <section class="py-20 px-4 md:px-8 max-w-[1100px] mx-auto">
      <div class="text-center mb-10">
        <div class="text-[11px] font-bold uppercase tracking-[0.12em] text-ocean-cyan mb-3">See it in action</div>
        <h2 class="text-[clamp(24px,3vw,36px)] font-extrabold text-mist-foam tracking-tight">
          Explore real simulations
        </h2>
      </div>
      <div v-if="demosLoading" class="text-center text-mist-slate text-sm py-8">Loading demos...</div>
      <div v-else-if="demos.length" class="grid grid-cols-1 md:grid-cols-3 gap-5">
        <DemoCard
          v-for="demo in demos" :key="demo.share_token"
          :share-url="demo.share_url" :title="demo.title" :description="`${demo.tier} tier`"
        />
      </div>
      <div v-else class="text-center text-mist-slate text-sm py-8">No demos available yet.</div>
    </section>

    <div class="max-w-[1100px] mx-auto h-px bg-gradient-to-r from-transparent via-mist-depth to-transparent" />

    <!-- Social Proof -->
    <section id="proof" class="py-20 px-4 md:px-8 max-w-[1100px] mx-auto text-center">
      <div class="text-[11px] font-bold uppercase tracking-[0.12em] text-ocean-cyan mb-3">Trusted by strategists</div>
      <h2 class="text-[clamp(24px,3vw,36px)] font-extrabold text-mist-foam tracking-tight">
        See what teams are building
      </h2>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mt-10">
        <ProofCard
          v-for="proof in proofs" :key="proof.author"
          :quote="proof.quote" :author="proof.author" :role="proof.role"
        />
      </div>
    </section>

    <div class="max-w-[1100px] mx-auto h-px bg-gradient-to-r from-transparent via-mist-depth to-transparent" />

    <!-- Pricing -->
    <section id="pricing" class="py-24 px-4 md:px-8 max-w-[1100px] mx-auto text-center">
      <div class="text-[11px] font-bold uppercase tracking-[0.12em] text-ocean-cyan mb-3">Simple pricing</div>
      <h2 class="text-[clamp(24px,3vw,36px)] font-extrabold text-mist-foam tracking-tight">
        Pay only for what you simulate
      </h2>
      <p class="text-[17px] text-mist-drift mt-2">No subscriptions. No hidden fees. Buy credits, run simulations.</p>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-5 mt-12">
        <PricingCard
          v-for="tier in pricingTiers" :key="tier.name"
          :name="tier.name" :credits="tier.credits" :price="tier.price"
          :features="tier.features" :accentColor="tier.accent" :featured="tier.featured"
        />
      </div>
    </section>

    <div class="max-w-[1100px] mx-auto h-px bg-gradient-to-r from-transparent via-mist-depth to-transparent" />

    <!-- Final CTA -->
    <section class="py-24 px-4 text-center relative overflow-hidden">
      <div class="absolute inset-0 pointer-events-none"
        style="background: radial-gradient(ellipse 70% 50% at 50% 50%, rgba(14,116,144,0.15), transparent), radial-gradient(ellipse 40% 40% at 30% 60%, rgba(255,107,107,0.05), transparent)"
      />
      <h2 class="relative text-[clamp(28px,4vw,44px)] font-extrabold text-mist-foam tracking-[-0.03em] mb-4">
        Ready to see what happens next?
      </h2>
      <p class="relative text-lg text-mist-drift mb-8">
        Upload your first document and watch the ecosystem come alive.
      </p>
      <router-link
        to="/register"
        class="relative inline-block px-10 py-4 rounded-xl text-lg font-bold text-white
               bg-gradient-to-br from-coral to-coral-amber
               glow-coral transition-all duration-250 ease-spring
               hover:glow-coral-lg hover:-translate-y-0.5"
      >
        Get started
      </router-link>
    </section>

    <!-- Footer -->
    <footer class="border-t border-mist-depth max-w-[1100px] mx-auto px-4 md:px-8 py-12 flex justify-between items-center text-sm text-mist-slate">
      <div class="flex items-center gap-2">
        <LogoWavePulse :size="24" :animated="false" />
        <span class="font-bold text-mist-drift">SimSwarm</span>
        <span>&copy; 2026</span>
      </div>
      <div class="flex gap-6">
        <a href="#" class="hover:text-mist-drift transition-colors">Privacy</a>
        <a href="#" class="hover:text-mist-drift transition-colors">Terms</a>
        <a href="#" class="hover:text-mist-drift transition-colors">Docs</a>
        <a href="#" class="hover:text-mist-drift transition-colors">GitHub</a>
      </div>
    </footer>
  </div>
</template>

<script setup>
import ScrollProgress from '../components/ScrollProgress.vue'
import HeroSwarm from '../components/HeroSwarm.vue'
import HeroRotatingText from '../components/HeroRotatingText.vue'
import ExperienceStep from '../components/ExperienceStep.vue'
import PricingCard from '../components/PricingCard.vue'
import ProofCard from '../components/ProofCard.vue'
import LogoWavePulse from '../components/LogoWavePulse.vue'
import DemoCard from '../components/DemoCard.vue'
import { listDemos } from '../api/demos.js'
import { getPacks } from '../api/billing.js'
import { ref, onMounted } from 'vue'
import {
  INSIGHTS as insights,
  PROOFS as proofs,
  buildPricingTiers,
  agentStyle,
} from '../data/landingContent.js'

const demos = ref([])
const demosLoading = ref(true)
const pricingTiers = ref([])

onMounted(async () => {
  try {
    demos.value = await listDemos()
  } catch (err) {
    console.error('Failed to load demos:', err)
  } finally {
    demosLoading.value = false
  }

  try {
    const packs = await getPacks()
    if (packs && packs.length > 0) {
      pricingTiers.value = buildPricingTiers(packs)
    }
  } catch (err) {
    console.error('Failed to load pricing packs:', err)
    // pricingTiers stays empty; section renders nothing rather than stale fake prices
  }
})
</script>

<style scoped>
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}
@keyframes swim {
  0% { transform: translate(0, 0); }
  25% { transform: translate(var(--x1), var(--y1)); }
  50% { transform: translate(var(--x2), var(--y2)); }
  75% { transform: translate(var(--x3), var(--y3)); }
  100% { transform: translate(var(--x4), var(--y4)); }
}
</style>
