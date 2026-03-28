# Wizard & Remaining Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the New Simulation page as a 3-step wizard, and restyle all remaining pages (Login, Register, Account, SimulationStatus, DemoResult, TierSelector, PipelineProgress) for the Deep Ocean theme.

**Architecture:** Create new wizard step components and rebuild NewSimulation.vue as a stepped flow. Restyle remaining pages by replacing light-theme Tailwind classes with Deep Ocean tokens — no structural changes, just color/spacing updates. Keep all existing script logic.

**Tech Stack:** Vue 3 (Composition API), Tailwind CSS with Deep Ocean tokens

**Spec reference:** Section 5 of `docs/superpowers/specs/2026-03-27-simswarm-visual-redesign.md`

---

## File Structure

```
frontend/src/
  components/
    wizard/
      WizardProgress.vue              # CREATE - 3-dot progress indicator
      WizardSeed.vue                  # CREATE - step 1 (upload/URL/paste)
      WizardGoal.vue                  # CREATE - step 2 (goal + suggestions)
      WizardLaunch.vue                # CREATE - step 3 (tier + explainer + cost)
      SeedTips.vue                    # CREATE - collapsible seed guidance
    TierSelector.vue                  # MODIFY - dark theme restyle
    PipelineProgress.vue              # MODIFY - dark theme restyle
  views/
    NewSimulation.vue                 # MODIFY - full rebuild as wizard
    Login.vue                         # MODIFY - dark theme restyle
    Register.vue                      # MODIFY - dark theme restyle
    Account.vue                       # MODIFY - dark theme restyle
    SimulationStatus.vue              # MODIFY - dark theme restyle
    DemoResult.vue                    # MODIFY - dark theme restyle
```

---

### Task 1: Wizard Progress Component

**Files:**
- Create: `frontend/src/components/wizard/WizardProgress.vue`

- [ ] **Step 1: Create WizardProgress.vue**

```vue
<template>
  <div class="flex items-center justify-center gap-0 mb-10">
    <template v-for="(step, i) in steps" :key="step.id">
      <div class="flex flex-col items-center gap-2 cursor-pointer" @click="$emit('go', i + 1)">
        <div
          class="w-3 h-3 rounded-full border-2 transition-all duration-400 ease-spring relative z-[2]"
          :class="i + 1 < current ? 'border-organic-sage bg-organic-sage shadow-[0_0_8px_rgba(16,185,129,0.3)]'
            : i + 1 === current ? 'border-ocean-glow bg-ocean-glow shadow-[0_0_12px_rgba(34,211,238,0.4)]'
            : 'border-mist-depth bg-transparent'"
        />
        <span class="text-[11px] transition-colors"
          :class="i + 1 === current ? 'text-ocean-glow' : i + 1 < current ? 'text-organic-sage' : 'text-mist-slate'">
          {{ step.label }}
        </span>
      </div>
      <div
        v-if="i < steps.length - 1"
        class="w-20 h-0.5 mb-5 relative overflow-hidden transition-colors"
        :class="i + 1 < current ? 'bg-organic-sage'
          : i + 1 === current ? 'bg-gradient-to-r from-organic-sage to-ocean-glow'
          : 'bg-mist-depth'"
      >
        <div
          v-if="i + 1 === current"
          class="absolute top-0 left-0 w-full h-full animate-shimmer"
          style="background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);"
        />
      </div>
    </template>
  </div>
</template>

<script setup>
defineProps({
  current: { type: Number, default: 1 },
})

defineEmits(['go'])

const steps = [
  { id: 'seed', label: 'Seed' },
  { id: 'goal', label: 'Goal' },
  { id: 'launch', label: 'Launch' },
]
</script>

<style scoped>
@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(200%); }
}
.animate-shimmer { animation: shimmer 2s infinite; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/wizard/WizardProgress.vue
git commit -m "feat: add WizardProgress 3-dot step indicator"
```

---

### Task 2: Wizard Step Components

**Files:**
- Create: `frontend/src/components/wizard/SeedTips.vue`
- Create: `frontend/src/components/wizard/WizardSeed.vue`
- Create: `frontend/src/components/wizard/WizardGoal.vue`
- Create: `frontend/src/components/wizard/WizardLaunch.vue`

- [ ] **Step 1: Create SeedTips.vue**

```vue
<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-xl overflow-hidden mb-5">
    <div class="flex items-center gap-2 px-4 py-3 text-sm font-semibold text-mist-drift cursor-pointer transition-colors hover:text-mist-foam hover:bg-ocean-abyss/50" @click="open = !open">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
      What makes a good seed?
      <span class="ml-auto text-[10px] text-mist-slate transition-transform" :class="open ? 'rotate-90' : ''">&#x25B6;</span>
    </div>
    <div v-if="open" class="px-4 pb-4 space-y-1.5">
      <div v-for="tip in tips" :key="tip.text" class="flex items-start gap-2.5 text-sm text-mist-drift leading-snug">
        <span class="flex-shrink-0 mt-0.5" :class="tip.cls">{{ tip.icon }}</span>
        <span><strong class="text-mist">{{ tip.bold }}</strong> {{ tip.text }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const open = ref(false)

const tips = [
  { icon: '✓', cls: 'text-organic-seafoam', bold: 'Specific events', text: '— an earnings report, a policy announcement, a product launch press release.' },
  { icon: '✓', cls: 'text-organic-seafoam', bold: 'Multiple stakeholders', text: '— documents mentioning companies, regulators, media, and public figures.' },
  { icon: '✓', cls: 'text-organic-seafoam', bold: 'Recent context', text: '— news articles or analyst notes from the last few days.' },
  { icon: '○', cls: 'text-coral-sand', bold: '2,000–20,000 characters', text: 'is the sweet spot. Too short = no context, too long = noise.' },
  { icon: '✗', cls: 'text-coral', bold: 'Avoid generic content', text: '— boilerplate pages or Wikipedia summaries won\'t produce interesting results.' },
]
</script>
```

- [ ] **Step 2: Create WizardSeed.vue**

```vue
<template>
  <div>
    <div class="mb-5">
      <div class="font-mono text-xs text-ocean-cyan tracking-wide mb-2">Step 1 of 3</div>
      <h2 class="text-3xl font-extrabold text-mist-foam tracking-tight leading-tight">Let's seed the ecosystem</h2>
      <p class="text-[15px] text-mist-drift mt-2">Upload a document or paste text to begin. The swarm will extract entities and build a knowledge graph.</p>
    </div>

    <SeedTips />

    <!-- Direct Upload -->
    <div class="text-[11px] font-semibold uppercase tracking-wider text-ocean-cyan mb-2">Direct Upload</div>
    <div
      class="border-2 border-dashed border-ocean-teal rounded-2xl p-7 text-center cursor-pointer transition-all hover:border-ocean-cyan"
      :class="isDragging ? 'border-ocean-glow bg-ocean-glow/5 scale-[1.01] shadow-[0_0_30px_rgba(34,211,238,0.1)_inset]' : 'bg-ocean-deep/40'"
      @dragover.prevent="isDragging = true"
      @dragleave="isDragging = false"
      @drop.prevent="handleDrop"
      @click="$refs.fileInput.click()"
    >
      <div v-if="fileName" class="flex items-center justify-center gap-3">
        <span class="text-2xl">&#x1F4C4;</span>
        <div class="text-left">
          <div class="text-sm font-semibold text-mist-foam">{{ fileName }}</div>
          <div class="text-xs text-mist-slate">{{ charCount }} characters extracted</div>
        </div>
        <button @click.stop="clearFile" class="text-mist-slate hover:text-coral text-lg ml-2">&times;</button>
      </div>
      <template v-else>
        <div class="text-3xl mb-1.5">&#x1F30A;</div>
        <div class="text-sm font-medium text-mist-drift">Drop your document here</div>
        <div class="text-xs text-mist-slate mt-1">or</div>
        <button class="mt-2 px-5 py-1.5 rounded-lg border border-ocean-teal text-sm font-semibold text-ocean-glow transition-all ease-spring hover:bg-ocean-cyan/15 hover:border-ocean-cyan hover:-translate-y-px" @click.stop="$refs.fileInput.click()">
          Browse files
        </button>
        <div class="font-mono text-[11px] text-mist-slate/60 mt-3">PDF, DOCX, TXT, Markdown — up to 50,000 characters</div>
      </template>
    </div>
    <input ref="fileInput" type="file" class="hidden" accept=".pdf,.docx,.txt,.md" @change="handleFileSelect" />

    <!-- Import from Source -->
    <div class="text-[11px] font-semibold uppercase tracking-wider text-ocean-cyan mt-6 mb-2">Import from Source</div>
    <div class="flex items-center bg-ocean-abyss border border-mist-depth rounded-xl p-1 pl-3.5 gap-2 transition-all focus-within:border-ocean-cyan focus-within:shadow-[0_0_0_3px_rgba(14,116,144,0.15)]">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
      <input v-model="url" type="url" placeholder="https://example.com/press-release" class="flex-1 bg-transparent border-none outline-none text-sm text-mist py-2" />
      <button @click="fetchUrl" :disabled="fetchingUrl" class="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gradient-to-br from-ocean-cyan to-cyan-500 text-white text-sm font-semibold whitespace-nowrap transition-all ease-spring hover:-translate-y-px disabled:opacity-50">
        {{ fetchingUrl ? 'Fetching...' : 'Fetch' }}
      </button>
    </div>
    <div v-if="urlStatus" class="text-xs mt-2" :class="urlError ? 'text-coral' : 'text-organic-seafoam'">{{ urlStatus }}</div>

    <!-- Raw Input -->
    <div class="text-[11px] font-semibold uppercase tracking-wider text-ocean-cyan mt-6 mb-2">Raw Input</div>
    <textarea
      v-model="seedText"
      placeholder="Paste your document text here — news articles, reports, announcements, policy drafts..."
      class="w-full bg-ocean-abyss border border-mist-depth rounded-xl p-3.5 text-sm text-mist resize-vertical min-h-[90px] outline-none transition-all focus:border-ocean-cyan focus:shadow-[0_0_0_3px_rgba(14,116,144,0.15)]"
    />
    <div class="font-mono text-[11px] text-mist-slate text-right mt-1">{{ seedText.length }} / 50,000</div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import SeedTips from './SeedTips.vue'

const emit = defineEmits(['update:seedText'])

const seedText = ref('')
const fileName = ref('')
const charCount = ref(0)
const isDragging = ref(false)
const url = ref('')
const fetchingUrl = ref(false)
const urlStatus = ref('')
const urlError = ref(false)

function handleDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer.files[0]
  if (file) processFile(file)
}

function handleFileSelect(e) {
  const file = e.target.files[0]
  if (file) processFile(file)
}

function processFile(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    seedText.value = e.target.result
    fileName.value = file.name
    charCount.value = e.target.result.length
    emit('update:seedText', seedText.value)
  }
  reader.readAsText(file)
}

function clearFile() {
  fileName.value = ''
  charCount.value = 0
  seedText.value = ''
  emit('update:seedText', '')
}

async function fetchUrl() {
  if (!url.value.trim()) return
  fetchingUrl.value = true
  urlStatus.value = ''
  urlError.value = false
  // TODO: wire to backend URL fetch endpoint
  // For now, show that it would work
  setTimeout(() => {
    urlStatus.value = 'URL fetching requires a backend endpoint (not yet implemented)'
    urlError.value = true
    fetchingUrl.value = false
  }, 1000)
}
</script>
```

- [ ] **Step 3: Create WizardGoal.vue**

```vue
<template>
  <div>
    <div class="mb-5">
      <div class="font-mono text-xs text-ocean-cyan tracking-wide mb-2">Step 2 of 3</div>
      <h2 class="text-3xl font-extrabold text-mist-foam tracking-tight leading-tight">What do you want to know?</h2>
      <p class="text-[15px] text-mist-drift mt-2">Describe your research question. The swarm will simulate how stakeholders, markets, and media react.</p>
    </div>

    <textarea
      :value="goal"
      @input="$emit('update:goal', $event.target.value)"
      placeholder="e.g. How will the market react to our Q1 earnings miss? What public sentiment shifts should we expect?"
      class="w-full bg-ocean-abyss border border-mist-depth rounded-2xl p-5 text-base text-mist resize-none min-h-[140px] outline-none leading-relaxed transition-all focus:border-ocean-cyan focus:shadow-[0_0_0_3px_rgba(14,116,144,0.15)]"
    />

    <div class="text-[11px] font-semibold uppercase tracking-wider text-mist-slate mt-5 mb-2.5">Try a prompt</div>
    <div class="flex flex-wrap gap-2">
      <button
        v-for="s in suggestions" :key="s"
        @click="$emit('update:goal', s)"
        class="text-sm text-mist-drift bg-ocean-deep border border-mist-depth px-4 py-2 rounded-xl transition-all ease-spring hover:bg-ocean-cyan/12 hover:border-ocean-cyan hover:text-ocean-glow hover:-translate-y-0.5"
      >
        {{ s }}
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  goal: { type: String, default: '' },
})

defineEmits(['update:goal'])

const suggestions = [
  'How will the market react to...',
  'What will public sentiment be if...',
  'How will stakeholders respond to...',
  'What narrative will form around...',
  'What coalitions will emerge after...',
]
</script>
```

- [ ] **Step 4: Create WizardLaunch.vue**

```vue
<template>
  <div>
    <div class="mb-5">
      <div class="font-mono text-xs text-ocean-cyan tracking-wide mb-2">Step 3 of 3</div>
      <h2 class="text-3xl font-extrabold text-mist-foam tracking-tight leading-tight">Choose your ecosystem size</h2>
      <p class="text-[15px] text-mist-drift mt-2">Larger ecosystems produce richer simulations with more diverse agent interactions.</p>
    </div>

    <!-- Tier cards -->
    <div class="grid grid-cols-3 gap-3 mb-5">
      <button
        v-for="tier in tiers" :key="tier.id"
        @click="selectTier(tier.id)"
        :disabled="!creditsStore.canAfford(tier.id)"
        class="relative overflow-hidden rounded-2xl border-2 p-5 text-center transition-all duration-350 ease-spring"
        :class="[
          selectedTier === tier.id
            ? 'border-[var(--border)] bg-ocean-abyss shadow-[0_0_24px_var(--glow)]'
            : 'border-mist-depth bg-ocean-deep hover:border-[var(--border)] hover:-translate-y-1',
          !creditsStore.canAfford(tier.id) ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer',
        ]"
        :style="{ '--glow': tier.glow, '--border': tier.border, '--accent': tier.accent }"
      >
        <div class="text-base font-bold text-mist-foam transition-colors" :class="selectedTier === tier.id ? '' : ''" :style="selectedTier === tier.id ? { color: tier.accent } : {}">{{ tier.label }}</div>
        <div class="font-mono text-[11px] text-mist-slate">{{ tier.range }}</div>
        <div class="text-2xl font-extrabold mt-3 transition-transform" :style="{ color: tier.accent }" :class="selectedTier === tier.id ? 'scale-105' : ''">{{ creditsStore.getTierCost(tier.id) }} cr</div>
        <div class="text-[11px] text-mist-slate mt-1">{{ tier.duration }}</div>
      </button>
    </div>

    <!-- Size explainer -->
    <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5 mb-5">
      <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate text-center mb-4">How size affects your simulation</div>
      <div class="flex items-center justify-center gap-1">
        <div v-for="(s, i) in sizeInfo" :key="s.label" class="flex items-center gap-1">
          <div class="text-center flex-1 max-w-[140px]">
            <div class="h-16 relative mb-2">
              <span v-for="dot in s.dots" :key="dot.x" class="absolute rounded-full opacity-80" :style="{ left: dot.x, top: dot.y, width: dot.s, height: dot.s, background: dot.c, boxShadow: '0 0 6px ' + dot.c }" />
            </div>
            <div class="text-xs font-bold" :style="{ color: s.color }">{{ s.label }}</div>
            <div class="text-[10px] text-mist-slate leading-snug mt-1" v-for="t in s.traits" :key="t">{{ t }}</div>
          </div>
          <svg v-if="i < sizeInfo.length - 1" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#334155" stroke-width="1.5" class="flex-shrink-0 mb-8"><polyline points="9 6 15 12 9 18"/></svg>
        </div>
      </div>
    </div>

    <!-- Cost summary -->
    <div class="bg-ocean-deep border border-mist-depth rounded-xl p-5 flex items-center justify-between">
      <div>
        <div class="text-sm text-mist-drift">Simulation cost</div>
        <div class="font-mono text-xl font-bold text-ocean-glow">{{ selectedTier ? creditsStore.getTierCost(selectedTier) : 0 }} credits</div>
        <div class="text-xs text-mist-slate mt-0.5">Balance after: <strong class="text-organic-seafoam">{{ balanceAfter }} credits</strong></div>
      </div>
      <div class="text-right">
        <div class="text-xs text-mist-slate">Current balance</div>
        <div class="font-mono text-base font-semibold text-organic-seafoam">{{ creditsStore.balance }} credits</div>
      </div>
    </div>

    <div v-if="creditsStore.isLow" class="flex items-center gap-2 mt-3 px-4 py-2.5 rounded-xl bg-coral-amber/8 border border-coral-amber/20 text-coral-amber text-sm">
      Low credit balance. <router-link to="/account" class="font-semibold underline">Purchase more</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useCreditsStore } from '../../stores/credits.js'

const creditsStore = useCreditsStore()

const emit = defineEmits(['update:tier'])

const selectedTier = ref('medium')
emit('update:tier', 'medium')

const tiers = [
  { id: 'small', label: 'Small', range: '1–500 agents', duration: '< 30 min', accent: '#22D3EE', border: '#0E7490', glow: 'rgba(34,211,238,0.08)' },
  { id: 'medium', label: 'Medium', range: '501–2,000 agents', duration: '< 4 hours', accent: '#A78BFA', border: '#7C3AED', glow: 'rgba(167,139,250,0.08)' },
  { id: 'large', label: 'Large', range: '2,001–10,000 agents', duration: '< 12 hours', accent: '#FBBF24', border: '#D97706', glow: 'rgba(251,191,36,0.08)' },
]

const sizeInfo = [
  { label: 'Small', color: '#22D3EE', traits: ['Fewer perspectives', 'Faster results', 'Key trends only'],
    dots: [{x:'40%',y:'30%',s:'5px',c:'#22D3EE'},{x:'55%',y:'50%',s:'4px',c:'#A78BFA'},{x:'35%',y:'60%',s:'4px',c:'#6EE7B7'}] },
  { label: 'Medium', color: '#A78BFA', traits: ['Balanced depth', 'Coalition detection', 'Most popular'],
    dots: [{x:'30%',y:'20%',s:'5px',c:'#22D3EE'},{x:'60%',y:'25%',s:'4px',c:'#A78BFA'},{x:'25%',y:'50%',s:'4px',c:'#6EE7B7'},{x:'55%',y:'55%',s:'5px',c:'#FF6B6B'},{x:'45%',y:'70%',s:'3px',c:'#FBBF24'},{x:'70%',y:'45%',s:'4px',c:'#22D3EE'}] },
  { label: 'Large', color: '#FBBF24', traits: ['Maximum diversity', 'Emergent coalitions', 'Deepest insights'],
    dots: [{x:'20%',y:'15%',s:'4px',c:'#22D3EE'},{x:'45%',y:'12%',s:'5px',c:'#A78BFA'},{x:'70%',y:'20%',s:'3px',c:'#6EE7B7'},{x:'30%',y:'40%',s:'5px',c:'#FF6B6B'},{x:'55%',y:'45%',s:'4px',c:'#FBBF24'},{x:'15%',y:'60%',s:'4px',c:'#22D3EE'},{x:'65%',y:'55%',s:'3px',c:'#A78BFA'},{x:'40%',y:'70%',s:'5px',c:'#6EE7B7'},{x:'75%',y:'65%',s:'4px',c:'#FF6B6B'}] },
]

const balanceAfter = computed(() => {
  if (!selectedTier.value) return creditsStore.balance
  return Math.max(0, creditsStore.balance - creditsStore.getTierCost(selectedTier.value))
})

function selectTier(id) {
  if (!creditsStore.canAfford(id)) return
  selectedTier.value = id
  emit('update:tier', id)
}
</script>
```

- [ ] **Step 5: Verify build**

Run: `cd frontend && npm run build`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/wizard/
git commit -m "feat: add wizard step components (SeedTips, WizardSeed, WizardGoal, WizardLaunch)"
```

---

### Task 3: Rebuild NewSimulation.vue as Wizard

**Files:**
- Modify: `frontend/src/views/NewSimulation.vue`

- [ ] **Step 1: Read the current NewSimulation.vue** to understand the data flow and submission logic.

- [ ] **Step 2: Replace NewSimulation.vue** with a 3-step wizard that:
- Uses `WizardProgress` at top
- Shows `WizardSeed` (step 1), `WizardGoal` (step 2), `WizardLaunch` (step 3)
- Has Back/Continue navigation with fade-slide transition
- Continue button is cyan gradient with arrow, Launch button is coral gradient with rocket icon
- Keeps the existing `handleSubmit` logic (createJob API call, credit deduction, router push)
- Centered layout (max-w-[640px]), navbar back link

The implementer should read the existing file first and keep the script logic (onMounted balance fetch, canSubmit computed, handleSubmit function). Replace the template with the wizard flow. Import WizardProgress, WizardSeed, WizardGoal, WizardLaunch. Use a `currentStep` ref (1/2/3) to toggle visibility.

- [ ] **Step 3: Verify build and test**

Run: `cd frontend && npm run build && npm test -- --run`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/NewSimulation.vue
git commit -m "feat: rebuild NewSimulation as 3-step wizard flow"
```

---

### Task 4: Restyle TierSelector + PipelineProgress

**Files:**
- Modify: `frontend/src/components/TierSelector.vue`
- Modify: `frontend/src/components/PipelineProgress.vue`

- [ ] **Step 1: Restyle TierSelector.vue**

Read the current file. Apply Dark Ocean class replacements:
- `text-gray-700` → `text-mist-drift`, `text-gray-900` → `text-mist-foam`, `text-gray-500` → `text-mist-slate`
- `border-gray-200` → `border-mist-depth`, `border-blue-500` → `border-ocean-cyan`, `bg-blue-50` → `bg-ocean-cyan/10`
- `ring-2 ring-blue-500` → `ring-2 ring-ocean-cyan`, `hover:border-blue-300` → `hover:border-ocean-teal`
- `text-blue-600` → `text-ocean-glow`, `text-red-500` → `text-coral`
- `bg-gray-50` → `bg-ocean-abyss/50`, `bg-white` → `bg-ocean-deep` (if present in disabled state)

- [ ] **Step 2: Restyle PipelineProgress.vue**

Read the current file. Apply Dark Ocean class replacements:
- `text-gray-700` → `text-mist-drift`, `text-gray-500` → `text-mist-slate`, `text-gray-400` → `text-mist-slate`
- `border-gray-200` → `border-mist-depth`, `bg-white` → `bg-ocean-deep`
- `border-green-400` → `border-organic-sage`, `bg-green-50` → `bg-organic-sage/10`, `text-green-600` → `text-organic-seafoam`
- `border-blue-500` → `border-ocean-cyan`, `bg-blue-50` → `bg-ocean-cyan/10`, `text-blue-600` → `text-ocean-glow`
- `bg-blue-600` → `bg-ocean-glow` (pulse dot)
- `bg-green-400` → `bg-organic-sage` (connecting line)
- `bg-gray-200` → `bg-mist-depth` (connecting line)

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/TierSelector.vue frontend/src/components/PipelineProgress.vue
git commit -m "feat: restyle TierSelector and PipelineProgress for dark ocean theme"
```

---

### Task 5: Restyle Login + Register

**Files:**
- Modify: `frontend/src/views/Login.vue`
- Modify: `frontend/src/views/Register.vue`

- [ ] **Step 1: Restyle Login.vue**

Read the current file. Replace all light-theme classes:
- Outer: `min-h-screen flex items-center justify-center bg-gray-50` → `min-h-screen flex items-center justify-center`
- Card: `bg-white rounded-lg shadow` → `bg-ocean-deep border border-mist-depth rounded-2xl`
- Title: `text-gray-900` → `text-mist-foam`
- Labels: `text-gray-700` → `text-mist-drift`
- Inputs: `border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500` → `border-mist-depth rounded-xl bg-ocean-abyss text-mist focus:ring-ocean-cyan focus:border-ocean-cyan focus:ring-2`
- Button: `bg-blue-600 hover:bg-blue-700` → `bg-gradient-to-br from-ocean-cyan to-cyan-500 glow-cyan hover:glow-cyan-lg hover:-translate-y-px transition-all ease-spring rounded-xl`
- Error: `bg-red-50 text-red-700` → `bg-coral/10 border border-coral/20 text-coral`
- Link: `text-blue-600` → `text-ocean-glow`
- Footer text: `text-gray-600` → `text-mist-slate`

- [ ] **Step 2: Restyle Register.vue**

Same pattern as Login. Also update:
- Success notice: `bg-blue-50 border-blue-200 text-blue-800` → `bg-ocean-cyan/10 border border-ocean-cyan/20 text-ocean-glow`

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/Login.vue frontend/src/views/Register.vue
git commit -m "feat: restyle Login and Register for dark ocean theme"
```

---

### Task 6: Restyle Account + SimulationStatus + DemoResult

**Files:**
- Modify: `frontend/src/views/Account.vue`
- Modify: `frontend/src/views/SimulationStatus.vue`
- Modify: `frontend/src/views/DemoResult.vue`

- [ ] **Step 1: Restyle Account.vue**

Read the current file. Apply Dark Ocean replacements throughout:
- All `bg-white border-gray-200` cards → `bg-ocean-deep border-mist-depth rounded-2xl`
- `text-gray-900/800` → `text-mist-foam`, `text-gray-500` → `text-mist-slate`, `text-gray-600` → `text-mist-drift`
- `text-blue-600` → `text-ocean-glow`, `text-green-600` → `text-organic-seafoam`, `text-red-600` → `text-coral`
- Purchase buttons: `hover:border-blue-300 hover:bg-blue-50` → `hover:border-ocean-teal hover:bg-ocean-cyan/10`
- Success/error banners: green/yellow/red → organic-sage/coral-amber/coral with ocean-themed opacity
- `divide-gray-100` → `divide-mist-depth`
- Balance number: `text-4xl font-bold text-blue-600` → `text-4xl font-bold text-ocean-glow`

- [ ] **Step 2: Restyle SimulationStatus.vue**

Read the current file. Apply Dark Ocean replacements:
- Cards: `bg-white border-gray-200` → `bg-ocean-deep border-mist-depth rounded-2xl`
- Status classes: update `statusClass` function to return dark theme classes
- `text-gray-900/800` → `text-mist-foam`, `text-gray-500` → `text-mist-slate`
- Back link: `text-blue-600` → `text-ocean-glow`
- Completed: `bg-green-600 text-white` → `bg-gradient-to-br from-ocean-cyan to-cyan-500 text-white`
- Failed: `bg-red-50 border-red-200 text-red-700` → `bg-coral/10 border border-coral/20 text-coral`

- [ ] **Step 3: Restyle DemoResult.vue**

Read the current file. Apply the same Dark Ocean class replacements used in SimulationResults.vue. This page has a very similar structure. Key changes:
- All `bg-white border-gray-200` → `bg-ocean-deep border-mist-depth`
- All text grays → mist equivalents
- All blues → ocean-cyan/ocean-glow
- Breadcrumb: `text-gray-400/600` → `text-mist-slate/drift`
- Use `bg-ocean-abyss` for page background
- Remove any references to `dual` view mode (keep story/graph/report)

- [ ] **Step 4: Verify build and tests**

Run: `cd frontend && npm run build && npm test -- --run`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/Account.vue frontend/src/views/SimulationStatus.vue frontend/src/views/DemoResult.vue
git commit -m "feat: restyle Account, SimulationStatus, and DemoResult for dark ocean theme"
```
