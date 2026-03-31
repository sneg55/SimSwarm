<template>
  <div>
    <div class="text-[11px] font-semibold uppercase tracking-wider text-mist-slate mb-2.5">Start from a template</div>
    <div class="grid grid-cols-1 gap-2">
      <button
        v-for="tpl in templates"
        :key="tpl.id"
        @click="$emit('select', tpl.text)"
        class="text-left px-4 py-3 bg-ocean-deep border border-mist-depth rounded-xl transition-all ease-spring hover:bg-ocean-cyan/8 hover:border-ocean-cyan/50 hover:-translate-y-0.5 group"
      >
        <div class="flex items-center gap-2 mb-0.5">
          <span class="text-base">{{ tpl.icon }}</span>
          <span class="text-[12px] font-semibold text-ocean-glow group-hover:text-ocean-cyan transition-colors">{{ tpl.label }}</span>
        </div>
        <p class="text-[12px] text-mist-slate leading-snug line-clamp-2">{{ tpl.text }}</p>
      </button>
    </div>
  </div>
</template>

<script setup>
defineEmits(['select'])

const templates = [
  {
    id: 'market-reaction',
    icon: '📈',
    label: 'Market Reaction',
    text: 'How will retail investors, analysts, and institutional traders react to [event] over the next 30 days? What price narratives and sentiment shifts should we expect?',
  },
  {
    id: 'crisis-response',
    icon: '🚨',
    label: 'Crisis Response',
    text: 'What narratives will form around [crisis] and which stakeholder coalitions will emerge? How will public sentiment and media coverage evolve over the next two weeks?',
  },
  {
    id: 'policy-impact',
    icon: '⚖️',
    label: 'Policy Impact',
    text: 'How will [affected groups] respond to [policy change] and what regulatory cascades should we expect over the next quarter? Which coalitions will form in support or opposition?',
  },
  {
    id: 'competitive-dynamics',
    icon: '♟️',
    label: 'Competitive Dynamics',
    text: 'How will [industry players] reposition after [disruption]? What alliances and rivalries will form, and how will market share narratives shift over the next 60 days?',
  },
  {
    id: 'public-opinion',
    icon: '💬',
    label: 'Public Opinion',
    text: 'How will public sentiment shift across platforms and demographics following [event]? What opinion clusters and influencer coalitions will emerge over the next month?',
  },
]
</script>
