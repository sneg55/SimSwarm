# Results Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the SimulationResults page with three dark-themed views (Story/Graph/Report), consistent bottom action bar, and updated graph/report/chat components to match the Deep Ocean design system.

**Architecture:** Restyle existing components (GraphControls, GraphLegend, GraphDetailPanel, GraphSearchBar, ReportViewer, ChatReplay, ViewModeToggle, ExportButtons) for the dark theme. Create new shared components (ResultsToolbar, ResultsBottomBar). Create Story view sections (StoryTimeline, FindingCard, SentimentBars, CoalitionCard, ConfidenceGrid). Rebuild SimulationResults.vue to orchestrate all three views.

**Tech Stack:** Vue 3 (Composition API), Tailwind CSS with Deep Ocean tokens, Cytoscape.js (existing)

**Spec reference:** Section 6 of `docs/superpowers/specs/2026-03-27-simswarm-visual-redesign.md`

**Mockup reference:** `.superpowers/brainstorm/` — files `05-guided-story-results.html`, `06-graph-view.html`, `07-report-view.html`

---

## File Structure

```
frontend/src/
  components/
    results/
      ResultsToolbar.vue              # CREATE - breadcrumb + view toggle toolbar
      ResultsBottomBar.vue            # CREATE - consistent bottom action bar
      StoryTimeline.vue               # CREATE - left-side scroll progress dots
      FindingCard.vue                 # CREATE - key finding with accent bar + metric
      SentimentBars.vue               # CREATE - animated sentiment bar chart
      CoalitionCard.vue               # CREATE - coalition group card
      ConfidenceGrid.vue              # CREATE - three confidence score cards
      ReportToc.vue                   # CREATE - left-side table of contents
    ReportViewer.vue                  # MODIFY - dark prose styling
    ChatReplay.vue                    # MODIFY - dark theme restyle
    ViewModeToggle.vue                # MODIFY - dark segmented control
    ExportButtons.vue                 # KEEP (used by other pages) but not used in results
    graph/
      graphColors.js                  # MODIFY - update colors to match Deep Ocean palette
      GraphControls.vue               # MODIFY - dark icon buttons
      GraphLegend.vue                 # MODIFY - dark theme + sentiment section
      GraphDetailPanel.vue            # MODIFY - dark slide-in panel
      GraphSearchBar.vue              # MODIFY - dark search input
      GraphVisualization.vue          # MODIFY - dark wrapper, remove old bg styles
      GraphCanvas.vue                 # KEEP - Cytoscape logic unchanged
  views/
    SimulationResults.vue             # MODIFY - full rebuild with three views
```

---

### Task 1: Shared Results Components (Toolbar + Bottom Bar)

**Files:**
- Create: `frontend/src/components/results/ResultsToolbar.vue`
- Create: `frontend/src/components/results/ResultsBottomBar.vue`

- [ ] **Step 1: Create ResultsToolbar.vue**

Create `frontend/src/components/results/ResultsToolbar.vue`:

```vue
<template>
  <div class="fixed top-[52px] left-0 right-0 z-40 px-6 py-2 flex items-center justify-between glass border-b border-mist-depth/50">
    <div class="flex items-center gap-2 text-sm text-mist-slate">
      <router-link to="/dashboard" class="hover:text-mist-drift transition-colors">&larr; Dashboard</router-link>
      <span>/</span>
      <span class="text-mist-drift">{{ title }}</span>
    </div>
    <div class="flex items-center gap-3">
      <slot name="controls" />
      <ViewModeToggle v-if="showToggle" :modelValue="viewMode" @update:modelValue="$emit('update:viewMode', $event)" />
    </div>
  </div>
</template>

<script setup>
import ViewModeToggle from '../ViewModeToggle.vue'

defineProps({
  title: { type: String, default: 'Results' },
  viewMode: { type: String, default: 'story' },
  showToggle: { type: Boolean, default: true },
})

defineEmits(['update:viewMode'])
</script>
```

- [ ] **Step 2: Create ResultsBottomBar.vue**

Create `frontend/src/components/results/ResultsBottomBar.vue`:

```vue
<template>
  <div class="fixed bottom-0 left-0 right-0 z-40 px-6 py-3 flex items-center justify-center gap-2 glass border-t border-mist-depth/50">
    <button
      v-if="showPng"
      @click="$emit('export', 'png')"
      class="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-mist-drift bg-ocean-deep border border-mist-depth transition-all duration-250 ease-spring hover:border-ocean-teal hover:text-mist-foam hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(0,0,0,0.3)]"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
      Export as PNG
    </button>
    <button
      @click="$emit('export', 'pdf')"
      :disabled="pdfLoading"
      class="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-mist-drift bg-ocean-deep border border-mist-depth transition-all duration-250 ease-spring hover:border-ocean-teal hover:text-mist-foam hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(0,0,0,0.3)] disabled:opacity-50"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      {{ pdfLoading ? 'Generating...' : 'Export as PDF' }}
    </button>
    <button
      v-if="showJson"
      @click="$emit('export', 'json')"
      class="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-mist-drift bg-ocean-deep border border-mist-depth transition-all duration-250 ease-spring hover:border-ocean-teal hover:text-mist-foam hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(0,0,0,0.3)]"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/></svg>
      Export as JSON
    </button>
    <button
      v-if="showCsv"
      @click="$emit('export', 'csv')"
      class="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-mist-drift bg-ocean-deep border border-mist-depth transition-all duration-250 ease-spring hover:border-ocean-teal hover:text-mist-foam hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(0,0,0,0.3)]"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
      Export as CSV
    </button>
    <button
      @click="$emit('share')"
      class="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white bg-gradient-to-br from-ocean-cyan to-cyan-500 glow-cyan transition-all duration-250 ease-spring hover:glow-cyan-lg hover:-translate-y-0.5"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg>
      Share simulation
    </button>
  </div>
</template>

<script setup>
defineProps({
  showPng: { type: Boolean, default: false },
  showJson: { type: Boolean, default: true },
  showCsv: { type: Boolean, default: true },
  pdfLoading: { type: Boolean, default: false },
})

defineEmits(['export', 'share'])
</script>
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/results/
git commit -m "feat: add ResultsToolbar and ResultsBottomBar components"
```

---

### Task 2: Restyle ViewModeToggle for Dark Theme

**Files:**
- Modify: `frontend/src/components/ViewModeToggle.vue`

- [ ] **Step 1: Replace ViewModeToggle.vue**

```vue
<template>
  <div class="inline-flex gap-0.5 bg-ocean-deep border border-mist-depth rounded-xl p-0.5">
    <button
      v-for="mode in availableModes"
      :key="mode.value"
      @click="$emit('update:modelValue', mode.value)"
      class="px-3.5 py-1.5 text-xs font-medium rounded-lg transition-all duration-250"
      :class="modelValue === mode.value
        ? 'bg-ocean-cyan/20 text-mist-foam'
        : 'text-mist-slate hover:text-mist-drift'"
    >
      {{ mode.label }}
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: 'story' },
  compact: { type: Boolean, default: false },
})

defineEmits(['update:modelValue'])

const allModes = [
  { value: 'story', label: 'Story' },
  { value: 'graph', label: 'Graph' },
  { value: 'report', label: 'Report' },
]

const availableModes = computed(() => {
  if (props.compact) return allModes.filter((m) => m.value !== 'dual')
  return allModes
})
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ViewModeToggle.vue
git commit -m "feat: restyle ViewModeToggle for dark ocean theme"
```

---

### Task 3: Restyle ReportViewer for Dark Theme

**Files:**
- Modify: `frontend/src/components/ReportViewer.vue`

- [ ] **Step 1: Replace ReportViewer.vue**

```vue
<template>
  <div class="report-prose" v-html="renderedMarkdown" />
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  content: { type: String, default: '' },
})

const renderedMarkdown = computed(() => {
  if (!props.content) return ''
  return props.content
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/^(?!<[hp])(.+)/gm, '<p>$1</p>')
})
</script>

<style scoped>
.report-prose :deep(h1) {
  font-size: 26px; font-weight: 800; color: #F1F5F9;
  letter-spacing: -0.02em;
  margin: 0 0 20px; padding-bottom: 16px;
  border-bottom: 1px solid #1E293B;
}
.report-prose :deep(h2) {
  font-size: 20px; font-weight: 700; color: #F1F5F9;
  letter-spacing: -0.01em; margin: 36px 0 14px;
}
.report-prose :deep(h3) {
  font-size: 16px; font-weight: 600; color: #CBD5E1;
  margin: 28px 0 10px;
}
.report-prose :deep(p) {
  font-size: 15px; color: #CBD5E1; line-height: 1.8;
  margin-bottom: 16px;
}
.report-prose :deep(strong) { color: #F1F5F9; font-weight: 600; }
.report-prose :deep(em) { color: #94A3B8; }
.report-prose :deep(code) {
  font-family: 'JetBrains Mono', monospace; font-size: 13px;
  background: rgba(34, 211, 238, 0.08); color: #22D3EE;
  padding: 2px 6px; border-radius: 4px;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ReportViewer.vue
git commit -m "feat: restyle ReportViewer for dark ocean theme"
```

---

### Task 4: Restyle ChatReplay for Dark Theme

**Files:**
- Modify: `frontend/src/components/ChatReplay.vue`

- [ ] **Step 1: Replace ChatReplay.vue**

```vue
<template>
  <div>
    <div class="border border-mist-depth rounded-2xl overflow-hidden bg-ocean-deep">
      <div
        class="px-6 py-4 border-b border-mist-depth flex items-center justify-between cursor-pointer transition-colors hover:bg-ocean-abyss/50"
        @click="expanded = !expanded"
      >
        <div class="flex items-center gap-2 text-[15px] font-semibold text-mist-foam">
          <span class="text-xs transition-transform" :class="expanded ? 'rotate-90' : ''">&#x25B6;</span>
          Agent Chat Replay
        </div>
        <span class="font-mono text-xs text-mist-slate bg-ocean-abyss px-2 py-0.5 rounded-lg">
          {{ messages.length }} messages
        </span>
      </div>
      <div v-if="expanded" ref="chatContainer" class="max-h-[500px] overflow-y-auto p-4 space-y-2" style="scrollbar-width: thin; scrollbar-color: #164E63 #0B1426;">
        <div v-if="messages.length === 0" class="text-center text-mist-slate text-sm py-8">No messages.</div>
        <div
          v-for="(msg, idx) in messages" :key="idx"
          class="max-w-[85%] px-3.5 py-2.5 rounded-xl text-sm"
          :class="msg.role === 'user'
            ? 'ml-auto bg-ocean-cyan/20 text-mist-foam'
            : msg.role === 'system'
            ? 'max-w-none text-center bg-coral-sand/5 border border-coral-sand/12 text-coral-sand text-xs font-medium'
            : 'bg-ocean-abyss border border-mist-depth text-mist'"
        >
          <div v-if="msg.role === 'assistant'" class="text-[11px] font-semibold mb-1" :style="{ color: agentColor(msg.agent) }">
            {{ msg.agent || 'Agent' }}
          </div>
          <div class="whitespace-pre-wrap">{{ msg.content }}</div>
          <div v-if="msg.timestamp" class="text-[10px] text-mist-slate/50 mt-1 text-right">
            {{ formatTime(msg.timestamp) }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  startExpanded: { type: Boolean, default: false },
})

const expanded = ref(props.startExpanded)
const chatContainer = ref(null)

const AGENT_COLORS = {
  default: '#94A3B8',
}

function agentColor(agent) {
  if (!agent) return AGENT_COLORS.default
  // Hash agent name to pick a color from the palette
  const palette = ['#22D3EE', '#A78BFA', '#6EE7B7', '#FF6B6B', '#FBBF24', '#F97316']
  let hash = 0
  for (let i = 0; i < agent.length; i++) hash = ((hash << 5) - hash + agent.charCodeAt(i)) | 0
  return palette[Math.abs(hash) % palette.length]
}

watch(
  () => props.messages.length,
  async () => {
    await nextTick()
    if (chatContainer.value) chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
)

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ChatReplay.vue
git commit -m "feat: restyle ChatReplay for dark ocean theme with collapsible header"
```

---

### Task 5: Restyle Graph Components for Dark Theme

**Files:**
- Modify: `frontend/src/components/graph/graphColors.js`
- Modify: `frontend/src/components/graph/GraphControls.vue`
- Modify: `frontend/src/components/graph/GraphLegend.vue`
- Modify: `frontend/src/components/graph/GraphDetailPanel.vue`
- Modify: `frontend/src/components/graph/GraphSearchBar.vue`
- Modify: `frontend/src/components/graph/GraphVisualization.vue`

This is the largest task — restyle all 6 graph files for the Dark Ocean theme. Read each file first, then apply these changes:

- [ ] **Step 1: Update graphColors.js**

Replace `frontend/src/components/graph/graphColors.js`:

```javascript
const ENTITY_COLORS = {
  University: '#f97316',
  Entity: '#22D3EE',
  Alumni: '#FF6B6B',
  Organization: '#22D3EE',
  Student: '#FF6B6B',
  Professor: '#F97316',
  Person: '#A78BFA',
  MediaOutlet: '#6EE7B7',
  LegalAuthority: '#10B981',
  OpinionLeader: '#FBBF24',
  GovernmentAgency: '#FF6B6B',
}

const FALLBACK_PALETTE = [
  '#22D3EE', '#A78BFA', '#6EE7B7', '#FF6B6B', '#FBBF24',
  '#F97316', '#10B981', '#0E7490', '#64748B', '#CBD5E1',
]

const dynamicColorCache = {}

export function getEntityColor(entityType) {
  if (ENTITY_COLORS[entityType]) return ENTITY_COLORS[entityType]
  if (dynamicColorCache[entityType]) return dynamicColorCache[entityType]
  let hash = 0
  for (let i = 0; i < entityType.length; i++) {
    hash = ((hash << 5) - hash + entityType.charCodeAt(i)) | 0
  }
  const color = FALLBACK_PALETTE[Math.abs(hash) % FALLBACK_PALETTE.length]
  dynamicColorCache[entityType] = color
  return color
}

export function getPrimaryLabel(labels) {
  return labels.find((l) => l !== 'Entity' && l !== 'Node') || 'Entity'
}

export { ENTITY_COLORS }
```

- [ ] **Step 2: Restyle GraphControls.vue**

Read the current file, then replace all `bg-white` with `bg-ocean-deep`, `border-gray-200` with `border-mist-depth`, `text-gray-600` with `text-mist-slate`, `hover:bg-gray-50` with `hover:bg-ocean-teal/20`, `text-gray-700` with `text-mist-drift`, `bg-gray-300` with `bg-mist-depth`, `bg-indigo-500` with `bg-ocean-cyan`, `focus:ring-indigo-400` with `focus:ring-ocean-cyan`. Also add `shadow-sm` → remove or keep. Add `transition-all duration-250 ease-spring hover:-translate-y-px` to buttons.

- [ ] **Step 3: Restyle GraphLegend.vue**

Read the current file, then replace: `bg-white/90` → `bg-ocean-deep/90`, `border-gray-200` → `border-mist-depth`, `text-red-600` → `text-ocean-cyan`, `text-indigo-600` → `text-ocean-cyan`, `hover:text-indigo-800` → `hover:text-ocean-glow`, `text-gray-700` → `text-mist`, `text-gray-400` → `text-mist-slate`, `text-gray-500` → `text-mist-slate`, `hover:bg-gray-100` → `hover:bg-ocean-teal/10`, `border-gray-100` → `border-mist-depth`.

- [ ] **Step 4: Restyle GraphDetailPanel.vue**

Read the current file, then replace: `bg-white` → `bg-ocean-deep`, `border-gray-200` → `border-mist-depth`, `border-l` → `border-l border-mist-depth`, `text-gray-900` → `text-mist-foam`, `text-gray-600` → `text-mist-drift`, `text-gray-400` → `text-mist-slate`, `text-gray-500` → `text-mist-slate`, `hover:bg-gray-50` → `hover:bg-ocean-teal/10`, `hover:text-gray-600` → `hover:text-mist-drift`, `hover:text-indigo-500` → `hover:text-ocean-glow`.

- [ ] **Step 5: Restyle GraphSearchBar.vue**

Read the current file, then replace: `bg-white` → `bg-ocean-deep`, `border-gray-200` → `border-mist-depth`, `text-gray-400` → `text-mist-slate`, `text-gray-700` → `text-mist`, `placeholder-gray-400` → `placeholder-mist-slate/50`, `hover:bg-gray-50` → `hover:bg-ocean-teal/10`, `text-gray-800` → `text-mist-foam`, `bg-gray-100` → `bg-ocean-abyss`. Add `focus:ring-ocean-cyan focus:border-ocean-cyan` to the input.

- [ ] **Step 6: Restyle GraphVisualization.vue**

Read the current file. Replace: `bg-gray-50` → `bg-ocean-abyss`, `border-gray-200` → `border-mist-depth`, `bg-white/80` → `bg-ocean-abyss/80`, `text-indigo-500` → `text-ocean-glow`, `text-gray-500` → `text-mist-slate`, `text-red-600` → `text-coral`.

- [ ] **Step 7: Verify build**

Run: `cd frontend && npm run build`

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/graph/
git commit -m "feat: restyle all graph components for dark ocean theme"
```

---

### Task 6: Story View Components

**Files:**
- Create: `frontend/src/components/results/StoryTimeline.vue`
- Create: `frontend/src/components/results/FindingCard.vue`
- Create: `frontend/src/components/results/SentimentBars.vue`
- Create: `frontend/src/components/results/CoalitionCard.vue`
- Create: `frontend/src/components/results/ConfidenceGrid.vue`

- [ ] **Step 1: Create StoryTimeline.vue**

```vue
<template>
  <div class="fixed left-6 top-1/2 -translate-y-1/2 z-30 flex flex-col gap-0">
    <template v-for="(section, i) in sections" :key="section.id">
      <div
        class="flex items-center gap-2.5 py-2 cursor-pointer group"
        @click="scrollToSection(section.id)"
      >
        <div
          class="w-2 h-2 rounded-full transition-all duration-300 flex-shrink-0"
          :class="i === activeIndex
            ? 'bg-ocean-glow shadow-[0_0_8px_rgba(34,211,238,0.5)]'
            : i < activeIndex ? 'bg-ocean-teal' : 'bg-mist-depth'"
        />
        <span
          class="text-[11px] text-mist-slate whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity"
        >
          {{ section.label }}
        </span>
      </div>
      <div
        v-if="i < sections.length - 1"
        class="w-0.5 h-6 ml-[3px] transition-colors duration-300"
        :class="i < activeIndex ? 'bg-ocean-teal' : i === activeIndex ? 'bg-gradient-to-b from-ocean-glow to-ocean-teal' : 'bg-mist-depth'"
      />
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  sections: { type: Array, required: true },
})

const activeIndex = ref(0)

function onScroll() {
  for (let i = props.sections.length - 1; i >= 0; i--) {
    const el = document.getElementById(props.sections[i].id)
    if (el && el.getBoundingClientRect().top < window.innerHeight * 0.4) {
      activeIndex.value = i
      return
    }
  }
  activeIndex.value = 0
}

function scrollToSection(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onUnmounted(() => window.removeEventListener('scroll', onScroll))
</script>
```

- [ ] **Step 2: Create FindingCard.vue**

```vue
<template>
  <div
    class="bg-ocean-deep border border-mist-depth rounded-xl p-6 mb-4 transition-transform duration-300 hover:translate-x-1"
    :style="{ borderLeftWidth: '3px', borderLeftColor: accentColor }"
  >
    <div class="font-mono text-xs tracking-wide mb-1.5" :style="{ color: accentColor }">
      {{ label }}
    </div>
    <h4 class="text-base font-bold text-mist-foam mb-2">{{ title }}</h4>
    <p class="text-[15px] text-mist leading-relaxed">{{ description }}</p>
    <div
      v-if="metric"
      class="inline-flex items-center gap-1.5 mt-3 font-mono text-sm px-2.5 py-1 rounded-md"
      :style="{ color: accentColor, background: accentColor + '14' }"
    >
      <span class="w-1.5 h-1.5 rounded-full" :style="{ background: accentColor }" />
      {{ metric }}
    </div>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  title: { type: String, required: true },
  description: { type: String, required: true },
  metric: { type: String, default: '' },
  accentColor: { type: String, default: '#22D3EE' },
})
</script>
```

- [ ] **Step 3: Create SentimentBars.vue**

```vue
<template>
  <div ref="containerRef" class="bg-ocean-deep border border-mist-depth rounded-2xl p-7">
    <div v-for="bar in bars" :key="bar.label" class="flex items-center gap-4 mb-4 last:mb-0">
      <span class="text-sm font-medium text-mist-drift min-w-[120px]">{{ bar.label }}</span>
      <div class="flex-1 h-2 bg-ocean-abyss rounded-full overflow-hidden">
        <div
          class="h-full rounded-full transition-[width] duration-[1.5s] ease-smooth"
          :style="{ width: (visible ? bar.width : 0) + '%', background: bar.gradient }"
        />
      </div>
      <span class="font-mono text-sm min-w-[48px] text-right" :style="{ color: bar.valueColor }">
        {{ bar.value }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

defineProps({
  bars: { type: Array, required: true },
})

const containerRef = ref(null)
const visible = ref(false)
let observer = null

onMounted(() => {
  observer = new IntersectionObserver(
    ([entry]) => { if (entry.isIntersecting) visible.value = true },
    { threshold: 0.3 }
  )
  if (containerRef.value) observer.observe(containerRef.value)
})

onUnmounted(() => observer?.disconnect())
</script>
```

- [ ] **Step 4: Create CoalitionCard.vue**

```vue
<template>
  <div class="bg-ocean-abyss border border-mist-depth rounded-xl p-4 transition-all duration-300 hover:border-ocean-teal hover:-translate-y-0.5">
    <div class="flex items-center gap-2 text-sm font-semibold text-mist-foam mb-1">
      <span class="w-2 h-2 rounded-full" :style="{ background: color, boxShadow: `0 0 8px ${color}66` }" />
      {{ name }}
    </div>
    <p class="text-sm text-mist-drift leading-snug">{{ description }}</p>
    <div class="font-mono text-[11px] text-mist-slate mt-2">
      {{ agents }} agents &middot; Strength: {{ strength }}%
    </div>
  </div>
</template>

<script setup>
defineProps({
  name: { type: String, required: true },
  description: { type: String, required: true },
  agents: { type: Number, required: true },
  strength: { type: Number, required: true },
  color: { type: String, default: '#22D3EE' },
})
</script>
```

- [ ] **Step 5: Create ConfidenceGrid.vue**

```vue
<template>
  <div class="grid grid-cols-3 gap-3">
    <div
      v-for="item in items" :key="item.label"
      class="bg-ocean-deep border border-mist-depth rounded-xl p-5 text-center transition-colors hover:border-ocean-teal"
    >
      <div class="font-mono text-3xl font-bold tracking-tight mb-1" :style="{ color: item.color }">
        {{ item.value }}
      </div>
      <div class="text-xs text-mist-slate uppercase tracking-wider">{{ item.label }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  items: { type: Array, required: true },
})
</script>
```

- [ ] **Step 6: Verify build**

Run: `cd frontend && npm run build`

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/results/
git commit -m "feat: add Story view components (timeline, finding, sentiment, coalition, confidence)"
```

---

### Task 7: Report Table of Contents

**Files:**
- Create: `frontend/src/components/results/ReportToc.vue`

- [ ] **Step 1: Create ReportToc.vue**

```vue
<template>
  <div class="fixed left-8 top-[120px] w-[200px] z-30 hidden xl:block">
    <div class="text-[11px] font-semibold uppercase tracking-wider text-mist-slate mb-3">Contents</div>
    <a
      v-for="(item, i) in items"
      :key="item.id"
      :href="`#${item.id}`"
      @click.prevent="scrollTo(item.id)"
      class="block text-xs py-1 border-l-2 transition-all duration-200"
      :class="[
        i === activeIndex ? 'text-ocean-glow border-ocean-glow' : 'text-mist-slate border-mist-depth hover:text-mist-drift hover:border-ocean-teal',
        item.sub ? 'pl-6' : 'pl-3',
      ]"
    >
      {{ item.label }}
    </a>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  items: { type: Array, required: true },
})

const activeIndex = ref(0)

function onScroll() {
  for (let i = props.items.length - 1; i >= 0; i--) {
    const el = document.getElementById(props.items[i].id)
    if (el && el.getBoundingClientRect().top < 150) {
      activeIndex.value = i
      return
    }
  }
  activeIndex.value = 0
}

function scrollTo(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onUnmounted(() => window.removeEventListener('scroll', onScroll))
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/results/ReportToc.vue
git commit -m "feat: add ReportToc component for left-side table of contents"
```

---

### Task 8: Rebuild SimulationResults.vue

**Files:**
- Modify: `frontend/src/views/SimulationResults.vue`

This is the main assembly task — rebuild SimulationResults.vue to use all the new components with three view modes (story/graph/report), consistent toolbar, and bottom action bar.

- [ ] **Step 1: Read the current SimulationResults.vue to understand the data flow**

The current file loads job data via `getJob(jobId)` and graph data via `getJobGraph(jobId)`. It has `viewMode`, `job`, `graphData`, `chatMessages` refs. Keep this data fetching logic, replace the template and add Story view.

- [ ] **Step 2: Replace SimulationResults.vue**

This is a large file. The key changes:
- Default view mode changes from `'report'` to `'story'`
- Template has three sections: story view (with StoryTimeline, FindingCard, SentimentBars, CoalitionCard, ConfidenceGrid, inline graph, ReportViewer, ChatReplay), graph view (existing GraphVisualization), and report view (ReportToc + ReportViewer + ChatReplay)
- ResultsToolbar at top, ResultsBottomBar at bottom
- All sections use dark ocean styling
- Export logic stays the same (PDF from server, JSON/CSV client-side)

The implementer should read the existing file first, then rebuild the template keeping the `<script setup>` data-loading logic. Import all new components. The Story view should parse `job.result_report` to extract sections for the timeline, findings from the report text, and display them with FindingCards. For the MVP, the Story view can show: simulation header card → full report (ReportViewer) → chat replay. The inline graph panel and scroll-driven animation are stretch goals for a future iteration.

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test -- --run`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/SimulationResults.vue
git commit -m "feat: rebuild SimulationResults with three dark-themed views (Story/Graph/Report)"
```
