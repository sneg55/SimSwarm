<template>
  <transition name="slide">
    <div
      v-if="node"
      class="absolute top-10 right-0 bottom-0 w-80 bg-ocean-deep/95 backdrop-blur-lg border-l border-mist-depth shadow-[0_0_40px_rgba(0,0,0,0.5)] overflow-y-auto z-30"
    >
      <div class="p-5">
        <!-- Close button -->
        <div class="flex justify-end mb-3">
          <button
            @click="$emit('close')"
            class="w-7 h-7 flex items-center justify-center rounded-full bg-ocean-abyss/60 border border-mist-depth text-mist-slate hover:text-mist-foam hover:border-ocean-teal transition-all"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Type badge -->
        <span
          class="inline-block text-[10px] font-bold tracking-widest uppercase px-2.5 py-1 rounded-md mb-3"
          :style="{ backgroundColor: nodeColor + '20', color: nodeColor, border: `1px solid ${nodeColor}40` }"
        >{{ node.entityType }}</span>

        <!-- Entity name -->
        <h3 class="text-xl font-bold text-mist-foam mb-3 leading-tight">{{ node.name }}</h3>

        <!-- Summary -->
        <p v-if="node.summary" class="text-sm text-mist-drift leading-relaxed mb-6">{{ node.summary }}</p>

        <!-- Relationships -->
        <div v-if="relationships.length > 0">
          <h4 class="text-[10px] font-bold tracking-widest text-mist-slate uppercase mb-3">
            Relationships ({{ relationships.length }})
          </h4>

          <div class="space-y-0.5">
            <button
              v-for="rel in relationships"
              :key="rel.target_uuid || rel.source_uuid || rel.targetName || rel.sourceName"
              @click="$emit('navigate-to', rel.direction === 'outgoing' ? rel.target_uuid : rel.source_uuid)"
              class="w-full flex items-center gap-2 px-2 py-2 text-left rounded-lg hover:bg-ocean-teal/10 transition-colors group"
            >
              <span class="text-xs text-mist-slate/60 group-hover:text-ocean-glow flex-shrink-0">
                {{ rel.direction === 'outgoing' ? '&rarr;' : '&larr;' }}
              </span>
              <span class="text-sm font-medium text-mist-foam truncate">
                {{ rel.direction === 'outgoing' ? (rel.targetName || rel.target_uuid) : (rel.sourceName || rel.source_uuid) }}
              </span>
              <span class="text-[10px] font-mono tracking-wide text-mist-slate/60 uppercase flex-shrink-0">
                {{ rel.type }}
              </span>
            </button>
          </div>
        </div>

        <!-- Properties -->
        <div v-if="node.connectionCount || node.sentiment || node.stance" class="mt-6 pt-4 border-t border-mist-depth/50">
          <div class="grid grid-cols-2 gap-3">
            <div v-if="node.connectionCount" class="text-center">
              <div class="font-mono text-lg font-bold" :style="{ color: nodeColor }">{{ node.connectionCount }}</div>
              <div class="text-[10px] text-mist-slate uppercase">Connections</div>
            </div>
            <div v-if="node.sentiment !== undefined && node.sentiment !== 0" class="text-center">
              <div class="font-mono text-lg font-bold"
                :style="{ color: node.sentiment > 0.2 ? '#6EE7B7' : node.sentiment < -0.2 ? '#FF6B6B' : '#94A3B8' }"
              >{{ node.sentiment > 0 ? '+' : '' }}{{ node.sentiment.toFixed(1) }}</div>
              <div class="text-[10px] text-mist-slate uppercase">Sentiment</div>
            </div>
            <div v-if="node.stance && node.stance !== 'neutral'" class="text-center">
              <div class="font-mono text-lg font-bold" :style="{ color: stanceColor }">{{ node.stance }}</div>
              <div class="text-[10px] text-mist-slate uppercase">Stance</div>
            </div>
            <div v-if="node.influenceWeight != null && node.influenceWeight !== 1.0" class="text-center">
              <div class="font-mono text-lg font-bold" :style="{ color: nodeColor }">{{ node.influenceWeight.toFixed(1) }}x</div>
              <div class="text-[10px] text-mist-slate uppercase">Influence</div>
            </div>
          </div>
        </div>

        <!-- Agent Activity -->
        <div v-if="agentActions.length > 0" class="mt-6 pt-4 border-t border-mist-depth/50">
          <h4 class="text-[10px] font-bold tracking-widest text-mist-slate uppercase mb-3">
            Activity ({{ dedupedActions.length }})
          </h4>

          <div class="space-y-2 max-h-[40vh] overflow-y-auto pr-1">
            <div
              v-for="(action, i) in dedupedActions"
              :key="i"
              class="rounded-lg bg-ocean-abyss/40 border border-mist-depth/30 px-3 py-2"
            >
              <div class="flex items-center gap-2 mb-1">
                <span class="text-[10px] font-mono font-bold uppercase px-1.5 py-0.5 rounded"
                  :class="actionBadgeClass(action.action_type)"
                >{{ actionLabel(action.action_type) }}</span>
                <span v-if="action.platforms.length" class="text-[10px] text-mist-slate/50">{{ action.platforms.join(', ') }}</span>
                <span class="text-[10px] text-mist-slate/40 ml-auto">R{{ action.round_num }}</span>
              </div>
              <p v-if="actionContent(action)" class="text-xs text-mist-drift leading-relaxed">
                {{ actionContent(action) }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed } from 'vue'
import { getEntityColor } from './graphColors.js'

const props = defineProps({
  node: { type: Object, default: null },
  agentActions: { type: Array, default: () => [] },
})

defineEmits(['close', 'navigate-to'])

const dedupedActions = computed(() => {
  const seen = new Map()
  for (const a of props.agentActions) {
    const content = a.action_args?.content || ''
    const key = `${a.action_type}:${a.round_num}:${content}`
    if (seen.has(key)) {
      const existing = seen.get(key)
      if (a.platform && !existing.platforms.includes(a.platform)) {
        existing.platforms.push(a.platform)
      }
    } else {
      seen.set(key, { ...a, platforms: [a.platform || ''].filter(Boolean) })
    }
  }
  return [...seen.values()]
})

const nodeColor = computed(() => {
  if (!props.node) return '#6b7280'
  return getEntityColor(props.node.entityType || 'Entity')
})

const stanceColor = computed(() => {
  const s = props.node?.stance
  if (s === 'supportive') return '#6EE7B7'
  if (s === 'opposing') return '#FF6B6B'
  if (s === 'observer') return '#94A3B8'
  return '#94A3B8'
})

const relationships = computed(() => {
  if (!props.node || !props.node.relationships) return []
  return props.node.relationships
})

function actionLabel(type) {
  const map = {
    CREATE_POST: 'Post',
    LIKE_POST: 'Like',
    REPOST: 'Repost',
    QUOTE_POST: 'Quote',
    FOLLOW: 'Follow',
    CREATE_COMMENT: 'Comment',
    LIKE_COMMENT: 'Like',
    DISLIKE_POST: 'Dislike',
    DISLIKE_COMMENT: 'Dislike',
    DO_NOTHING: 'Idle',
  }
  return map[type] || type
}

function actionBadgeClass(type) {
  if (['CREATE_POST', 'CREATE_COMMENT', 'QUOTE_POST'].includes(type))
    return 'bg-ocean-cyan/15 text-ocean-glow'
  if (['LIKE_POST', 'LIKE_COMMENT', 'REPOST'].includes(type))
    return 'bg-emerald-500/15 text-emerald-400'
  if (['DISLIKE_POST', 'DISLIKE_COMMENT'].includes(type))
    return 'bg-coral/15 text-coral'
  if (type === 'FOLLOW')
    return 'bg-organic-violet/15 text-organic-violet'
  return 'bg-mist-depth/30 text-mist-slate'
}

function actionContent(action) {
  return action.action_args?.content || ''
}
</script>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1),
              opacity 0.3s ease;
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>
