<template>
  <div>
    <!-- Under the hood -->
    <section id="engineering" class="py-20 px-4 md:px-8 max-w-[1100px] mx-auto">
      <div class="text-center mb-12">
        <div class="text-[11px] font-bold uppercase tracking-[0.12em] text-ocean-cyan mb-3">Under the hood</div>
        <h2 class="text-[clamp(24px,3vw,36px)] font-extrabold text-mist-foam tracking-tight text-balance">
          Built to read, run, and extend
        </h2>
        <p class="text-[17px] text-mist-drift mt-3 max-w-[600px] mx-auto text-pretty">
          A native engine with no black-box framework underneath. Self-host the whole stack and change anything.
        </p>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
        <a
          v-for="c in techCards" :key="c.title"
          :href="c.href" target="_blank" rel="noopener"
          class="group bg-ocean-abyss border border-mist-depth rounded-xl p-6 block
                 transition-[transform,border-color] duration-300 hover:-translate-y-0.5 hover:border-ocean-teal
                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ocean-cyan"
        >
          <div class="text-[11px] font-semibold uppercase tracking-wider text-ocean-cyan mb-2">{{ c.label }}</div>
          <div class="text-[17px] font-bold text-mist-foam mb-1.5">{{ c.title }}</div>
          <p class="text-sm text-mist-drift leading-relaxed text-pretty">{{ c.body }}</p>
          <div class="text-[13px] font-semibold text-ocean-cyan mt-3 opacity-0 group-hover:opacity-100 transition-opacity">Read the docs &#x2192;</div>
        </a>
      </div>
    </section>

    <div class="max-w-[1100px] mx-auto h-px bg-gradient-to-r from-transparent via-mist-depth to-transparent" />

    <!-- How it compares -->
    <section id="compare" class="py-20 px-4 md:px-8 max-w-[1100px] mx-auto">
      <div class="text-center mb-10">
        <div class="text-[11px] font-bold uppercase tracking-[0.12em] text-ocean-cyan mb-3">Lineage</div>
        <h2 class="text-[clamp(24px,3vw,36px)] font-extrabold text-mist-foam tracking-tight text-balance">
          How SimSwarm compares
        </h2>
        <p class="text-[17px] text-mist-drift mt-3 max-w-[640px] mx-auto text-pretty">
          SimSwarm grew out of the AGPL projects MiroFish and MiroShark, but shares no code with them.
          It is a native, MIT-licensed rewrite.
        </p>
      </div>
      <div class="overflow-x-auto rounded-xl border border-mist-depth">
        <table class="w-full text-left text-sm border-collapse min-w-[640px]">
          <thead>
            <tr class="bg-ocean-abyss">
              <th class="px-5 py-4 font-semibold text-mist-slate"></th>
              <th class="px-5 py-4 font-semibold text-mist-drift">MiroFish</th>
              <th class="px-5 py-4 font-semibold text-mist-drift">MiroShark</th>
              <th class="px-5 py-4 font-bold text-ocean-cyan">SimSwarm</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(dim, i) in comparison.dims" :key="dim" class="border-t border-mist-depth">
              <td class="px-5 py-4 font-semibold text-mist-foam whitespace-nowrap">{{ dim }}</td>
              <td class="px-5 py-4 text-mist-slate">{{ comparison.cols.MiroFish[i] }}</td>
              <td class="px-5 py-4 text-mist-slate">{{ comparison.cols.MiroShark[i] }}</td>
              <td class="px-5 py-4 text-mist-drift bg-ocean-teal/5">{{ comparison.cols.SimSwarm[i] }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="text-center mt-6">
        <a
          :href="DOCS_URL + '/introduction/lineage-and-differences'" target="_blank" rel="noopener"
          class="text-sm font-semibold text-ocean-cyan hover:text-ocean-teal transition-colors
                 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ocean-cyan"
        >
          Read the full lineage and differences &#x2192;
        </a>
      </div>
    </section>
  </div>
</template>

<script setup>
const DOCS_URL = 'https://docs.simswarm.xyz'

const techCards = [
  { label: 'Native engine', title: 'Async Python, no framework',
    body: 'The simswarm/ engine calls vLLM directly. No CAMEL-AI, no Flask, no subprocess. The whole agent loop is code you can read.',
    href: DOCS_URL + '/engine/architecture' },
  { label: 'Environments', title: 'Pluggable worlds',
    body: 'Agents act in social, market, and economic environments through a small tool interface. Register your own.',
    href: DOCS_URL + '/concepts/environments' },
  { label: 'Belief dynamics', title: 'Opinions that move',
    body: 'Each agent tracks stance, confidence, and trust. Updates are pure heuristic math, so opinion shifts cost no extra LLM calls.',
    href: DOCS_URL + '/engine/belief-formulation' },
  { label: 'Prediction markets', title: 'Agents put money on it',
    body: 'Per-sim binary markets with a constant-product AMM. Prices emerge from what the agents actually trade.',
    href: DOCS_URL + '/concepts/environments' },
  { label: 'Self-host stack', title: 'FastAPI, Temporal, your GPU',
    body: 'A Docker Compose stack runs the API, Temporal worker, Postgres, and Redis. Bring a RunPod key and an S3-compatible store.',
    href: DOCS_URL + '/self-hosting/architecture' },
  { label: 'Outputs', title: 'Report, graph, replay, API',
    body: 'Every run yields a structured report, an entity graph with typed relations, prediction-market data, and the full chat replay.',
    href: DOCS_URL + '/api/simswarm' },
]

const comparison = {
  dims: ['License', 'Engine runtime', 'Agent memory', 'Environments', 'Relationship'],
  cols: {
    MiroFish: ['AGPL-3.0', 'CAMEL-AI + Flask + per-sim SQLite', 'Stateless between rounds', 'Twitter + Reddit', 'Original engine'],
    MiroShark: ['AGPL-3.0', 'Forked from MiroFish', 'Belief state', 'Adds a prediction market', 'Fork of MiroFish'],
    SimSwarm: ['MIT', 'Native async, direct vLLM', 'Belief state (clean-room)', 'Pluggable: social / market / economic', 'Native rewrite, no shared code'],
  },
}
</script>
