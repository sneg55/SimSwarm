<template>
  <transition name="slide">
    <div
      v-if="node"
      class="absolute top-10 right-0 bottom-0 w-[420px] bg-ocean-deep/95 backdrop-blur-lg border-l border-mist-depth shadow-[0_0_40px_rgba(0,0,0,0.5)] overflow-y-auto z-30"
    >
      <div class="p-6">
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

        <!-- Agent Activity (social post style) -->
        <div v-if="agentActions.length > 0" class="mt-6 pt-4 border-t border-mist-depth/50">
          <h4 class="text-[10px] font-bold tracking-widest text-mist-slate uppercase mb-3">
            Activity ({{ dedupedActions.length }})
          </h4>

          <div class="space-y-3 max-h-[45vh] overflow-y-auto pr-1">
            <div
              v-for="(action, i) in dedupedActions"
              :key="i"
              class="rounded-xl border transition-colors"
              :class="platformCardClass(action.platforms)"
            >
              <!-- Post header -->
              <div class="flex items-center gap-2.5 px-4 pt-3 pb-2">
                <div class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
                  :style="{ backgroundColor: nodeColor + '25', color: nodeColor }">
                  {{ node.name?.charAt(0) || '?' }}
                </div>
                <div class="flex-1 min-w-0">
                  <div class="text-sm font-semibold text-mist-foam truncate">{{ node.name }}</div>
                  <div class="flex items-center gap-1.5 text-[10px] text-mist-slate">
                    <svg v-if="action.platforms.includes('twitter')" class="w-3 h-3" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                    <svg v-if="action.platforms.includes('reddit')" class="w-3 h-3" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z"/></svg>
                    <span>{{ action.platforms.join(', ') }}</span>
                    <span class="text-mist-depth">·</span>
                    <span>Round {{ action.round_num }}</span>
                  </div>
                </div>
                <span class="text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded-full"
                  :class="actionBadgeClass(action.action_type)"
                >{{ actionLabel(action.action_type) }}</span>
              </div>

              <!-- Post content -->
              <div v-if="actionContent(action)" class="px-4 pb-3">
                <p class="text-[13px] text-mist-drift leading-relaxed">{{ actionContent(action) }}</p>
              </div>

              <!-- Engagement bar (visual only) -->
              <div v-if="action.action_type === 'CREATE_POST' || action.action_type === 'CREATE_COMMENT'"
                class="flex items-center gap-6 px-4 py-2 border-t border-mist-depth/20 text-[10px] text-mist-slate/40">
                <span class="flex items-center gap-1">
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </span>
                <span class="flex items-center gap-1">
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path d="M17 1l4 4-4 4"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><path d="M7 23l-4-4 4-4"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>
                </span>
                <span class="flex items-center gap-1">
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
                </span>
              </div>
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

function platformCardClass(platforms) {
  if (platforms.includes('twitter'))
    return 'bg-[#0B1426] border-[#1D9BF0]/15 hover:border-[#1D9BF0]/30'
  if (platforms.includes('reddit'))
    return 'bg-[#0B1426] border-[#FF4500]/15 hover:border-[#FF4500]/30'
  return 'bg-ocean-abyss/40 border-mist-depth/30'
}

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
