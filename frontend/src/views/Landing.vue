<template>
  <div>
    <ScrollProgress />

    <!-- Hero -->
    <section class="relative min-h-screen flex flex-col justify-center items-center text-center pt-20">
      <div class="absolute inset-0 pointer-events-none"
        style="background: radial-gradient(ellipse 80% 60% at 50% 40%, rgba(14,116,144,0.12), transparent), radial-gradient(ellipse 60% 50% at 20% 80%, rgba(167,139,250,0.06), transparent), radial-gradient(ellipse 50% 40% at 80% 70%, rgba(255,107,107,0.04), transparent)"
      />

      <HeroSwarm />

      <h1 class="relative z-10 text-[clamp(36px,5vw,64px)] font-extrabold text-mist-foam tracking-[-0.03em] leading-[1.08] max-w-[720px] text-balance">
        See how<br>
        <HeroRotatingText /><br>
        could unfold.
      </h1>

      <p class="relative z-10 text-[clamp(16px,2vw,20px)] text-mist-drift max-w-[560px] mt-5 leading-relaxed text-pretty">
        SimSwarm is an open-source engine that runs swarms of LLM agents over a seed
        scenario, then surfaces a report, an entity graph, prediction markets, and the
        full chat replay. Explore real runs below, or deploy your own.
      </p>

      <div class="relative z-10 flex flex-wrap justify-center gap-4 mt-10">
        <a
          href="#demos"
          class="px-8 py-3.5 rounded-xl text-base font-bold text-white
                 bg-gradient-to-br from-coral to-coral-amber
                 glow-coral transition-[transform,box-shadow] duration-250 ease-spring
                 hover:glow-coral-lg hover:-translate-y-0.5
                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ocean-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-ocean-abyss"
        >
          Explore the demos
        </a>
        <a
          :href="GITHUB_URL" target="_blank" rel="noopener"
          class="px-8 py-3.5 rounded-xl text-base font-semibold text-mist
                 border border-mist-depth/60
                 transition-[color,background-color,border-color] duration-300
                 hover:border-mist-slate hover:bg-mist-depth/40 hover:text-mist-foam
                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ocean-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-ocean-abyss"
        >
          Deploy it yourself <span aria-hidden="true">&#x2197;</span>
        </a>
      </div>

      <div class="relative z-10 flex flex-wrap justify-center gap-x-8 gap-y-3 mt-12 text-sm text-mist-slate">
        <span class="flex items-center gap-1.5"><span aria-hidden="true">&#x2B50;</span> Open source (MIT)</span>
        <span class="flex items-center gap-1.5"><span aria-hidden="true">&#x1F433;</span> Self-host with docker&nbsp;compose</span>
        <span class="flex items-center gap-1.5"><span aria-hidden="true">&#x1F30A;</span> Bring your own GPU + LLM keys</span>
      </div>
    </section>

    <div class="max-w-[1100px] mx-auto h-px bg-gradient-to-r from-transparent via-mist-depth to-transparent" />

    <!-- Experience -->
    <section id="experience" class="px-4 md:px-8">
      <div class="text-center pt-24 pb-16 max-w-[1100px] mx-auto">
        <div class="text-[11px] font-bold uppercase tracking-[0.12em] text-ocean-cyan mb-3">How it works</div>
        <h2 class="text-[clamp(28px,3.5vw,40px)] font-extrabold text-mist-foam tracking-tight text-balance">
          From scenario to forecast in three steps.
        </h2>
        <p class="text-[17px] text-mist-drift mt-3 max-w-[540px] mx-auto text-pretty">
          Drop a document, set your question, and read what the agents do.
        </p>
      </div>

      <ExperienceStep stepNumber="01 — Seed the ecosystem">
        <template #title>Drop your document</template>
        <template #description>
          Upload a press release, policy draft, earnings report, or campaign brief.
          The agents read it, extract the entities, and build a knowledge graph of the
          stakeholders, forces, and narratives in play.
        </template>
        <template #detail>Supports PDF, DOCX, TXT, Markdown — up to 50,000 characters.</template>
        <template #mockup>
          <div class="border-2 border-dashed border-ocean-teal rounded-xl p-8 text-center transition-colors hover:border-ocean-cyan">
            <div class="text-4xl mb-2 animate-[float_4s_ease-in-out_infinite]" aria-hidden="true">&#x1F30A;</div>
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
          Dozens of LLM agents — each a market participant, journalist, regulator, or
          public voice — start interacting. Opinion clusters form, alliances shift, and
          consensus emerges round by round.
        </template>
        <template #detail>Replay the full agent conversation, post by post.</template>
        <template #mockup>
          <div class="relative h-[220px] overflow-hidden" aria-hidden="true">
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
          The run distills into a clear, scrollable narrative — key findings, sentiment
          shifts, and coalition maps. Readable at a glance, no analysis background
          required.
        </template>
        <template #detail>Export as PDF or CSV.</template>
        <template #mockup>
          <div class="text-xs text-mist-slate text-center mb-3 opacity-70">
            Illustrative example — what a finished report surfaces.
          </div>
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
    <section id="demos" class="py-20 px-4 md:px-8 max-w-[1100px] mx-auto">
      <div class="text-center mb-10">
        <div class="text-[11px] font-bold uppercase tracking-[0.12em] text-ocean-cyan mb-3">See it in action</div>
        <h2 class="text-[clamp(24px,3vw,36px)] font-extrabold text-mist-foam tracking-tight">
          Explore real simulations
        </h2>
      </div>
      <div aria-live="polite">
        <div v-if="demosLoading" class="text-center text-mist-slate text-sm py-8">Loading demos…</div>
        <div v-else-if="demos.length" class="grid grid-cols-1 md:grid-cols-3 gap-5">
          <DemoCard
            v-for="demo in demos" :key="demo.share_token"
            :share-url="demo.share_url" :title="demo.title" :description="demoDescription(demo)"
          />
        </div>
        <div v-else class="text-center text-mist-slate text-sm py-8">No demos available yet.</div>
      </div>
    </section>

    <div class="max-w-[1100px] mx-auto h-px bg-gradient-to-r from-transparent via-mist-depth to-transparent" />

    <LandingTech />

    <div class="max-w-[1100px] mx-auto h-px bg-gradient-to-r from-transparent via-mist-depth to-transparent" />

    <!-- Deploy your own -->
    <section class="py-24 px-4 text-center relative overflow-hidden">
      <div class="absolute inset-0 pointer-events-none"
        style="background: radial-gradient(ellipse 70% 50% at 50% 50%, rgba(14,116,144,0.15), transparent), radial-gradient(ellipse 40% 40% at 30% 60%, rgba(255,107,107,0.05), transparent)"
      />
      <h2 class="relative text-[clamp(28px,4vw,44px)] font-extrabold text-mist-foam tracking-[-0.03em] mb-4 text-balance">
        Run the whole swarm on your own infra
      </h2>
      <p class="relative text-lg text-mist-drift mb-8 max-w-[620px] mx-auto text-pretty">
        SimSwarm is open source. Clone the repo, bring your own GPU provider and LLM keys,
        and launch simulations from your own deployment.
      </p>
      <div class="relative inline-block text-left bg-ocean-abyss border border-mist-depth rounded-xl px-6 py-4 font-mono text-sm text-mist-drift mb-8 max-w-full overflow-x-auto">
        <div>git clone https://github.com/sneg55/SimSwarm</div>
        <div>cd SimSwarm &amp;&amp; cp .env.example .env</div>
        <div>docker compose up -d</div>
      </div>
      <div class="relative">
        <a
          :href="GITHUB_URL" target="_blank" rel="noopener"
          class="inline-block px-10 py-4 rounded-xl text-lg font-bold text-white
                 bg-gradient-to-br from-coral to-coral-amber
                 glow-coral transition-[transform,box-shadow] duration-250 ease-spring
                 hover:glow-coral-lg hover:-translate-y-0.5
                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ocean-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-ocean-abyss"
        >
          View on GitHub <span aria-hidden="true">&#x2197;</span>
        </a>
      </div>
    </section>

    <!-- Footer -->
    <footer class="border-t border-mist-depth max-w-[1100px] mx-auto px-4 md:px-8 py-12 flex flex-wrap gap-4 justify-between items-center text-sm text-mist-slate">
      <div class="flex items-center gap-2">
        <LogoWavePulse :size="24" :animated="false" />
        <span class="font-bold text-mist-drift">SimSwarm</span>
        <span>&copy; 2026</span>
      </div>
      <div class="flex gap-6">
        <a href="https://docs.simswarm.xyz" target="_blank" rel="noopener"
           class="hover:text-mist-drift transition-colors rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ocean-cyan">Docs</a>
        <a :href="`${GITHUB_URL}/blob/main/LICENSE`" target="_blank" rel="noopener"
           class="hover:text-mist-drift transition-colors rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ocean-cyan">License (MIT)</a>
        <a :href="GITHUB_URL" target="_blank" rel="noopener"
           class="hover:text-mist-drift transition-colors rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ocean-cyan">GitHub</a>
      </div>
    </footer>
  </div>
</template>

<script setup>
import ScrollProgress from '../components/ScrollProgress.vue'
import HeroSwarm from '../components/HeroSwarm.vue'
import HeroRotatingText from '../components/HeroRotatingText.vue'
import ExperienceStep from '../components/ExperienceStep.vue'
import LandingTech from '../components/LandingTech.vue'
import LogoWavePulse from '../components/LogoWavePulse.vue'
import DemoCard from '../components/DemoCard.vue'
import { listDemos } from '../api/demos.js'
import { ref, onMounted } from 'vue'
import { INSIGHTS as insights, agentStyle } from '../data/landingContent.js'

const GITHUB_URL = 'https://github.com/sneg55/SimSwarm'

const demos = ref([])
const demosLoading = ref(true)

function demoDescription(demo) {
  const tier = demo.tier
    ? demo.tier.charAt(0).toUpperCase() + demo.tier.slice(1)
    : 'Simulation'
  return `${tier} simulation · report, graph & replay`
}

onMounted(async () => {
  try {
    demos.value = await listDemos()
  } catch (err) {
    console.error('Failed to load demos:', err)
  } finally {
    demosLoading.value = false
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
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
  }
}
</style>
