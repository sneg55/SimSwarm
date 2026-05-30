<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-3">
      <InfoTooltip copyKey="topPostsFeed.header">Top Posts</InfoTooltip>
    </div>
    <div class="space-y-1 max-h-[400px] overflow-y-auto">
      <div v-for="post in posts" :key="post.post_id + post.platform"
        class="flex gap-3 p-3 rounded-xl hover:bg-ocean-abyss/50 transition-colors">
        <div class="flex-shrink-0 text-sm">{{ post.platform === 'twitter' ? '𝕏' : '📱' }}</div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2 mb-1">
            <span class="text-xs font-medium text-ocean-cyan truncate">{{ post.agent_name }}</span>
            <span class="text-[10px] text-mist-slate">{{ post.platform }}</span>
          </div>
          <p class="text-xs text-mist-drift leading-relaxed whitespace-pre-wrap break-words">{{ post.content }}</p>
          <div class="flex gap-3 mt-1.5 text-[10px] text-mist-slate">
            <InfoTooltip v-if="post.num_likes" copyKey="topPostsFeed.likes"><span class="inline-flex items-center gap-1 text-green-400"><svg class="w-3 h-3" viewBox="0 0 24 24" fill="currentColor"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>{{ post.num_likes }}</span></InfoTooltip>
            <InfoTooltip v-if="post.num_shares" copyKey="topPostsFeed.shares"><span class="inline-flex items-center gap-1"><svg class="w-3 h-3" viewBox="0 0 24 24" fill="currentColor"><path d="M23 7.5V2l-2.5 2.5C18.94 2.64 16.6 1.5 14 1.5c-4.14 0-7.5 3.36-7.5 7.5h2c0-3.03 2.47-5.5 5.5-5.5 1.9 0 3.58.97 4.56 2.44L16 8.5h7zm-16 9V22l2.5-2.5c1.56 1.86 3.9 3 6.5 3 4.14 0 7.5-3.36 7.5-7.5h-2c0 3.03-2.47 5.5-5.5 5.5-1.9 0-3.58-.97-4.56-2.44L14 15.5H7z"/></svg>{{ post.num_shares }}</span></InfoTooltip>
            <InfoTooltip v-if="post.num_dislikes" copyKey="topPostsFeed.dislikes"><span class="inline-flex items-center gap-1 text-red-400"><svg class="w-3 h-3" viewBox="0 0 24 24" fill="currentColor"><path d="M15 3H6c-.83 0-1.54.5-1.84 1.22l-3.02 7.05c-.09.23-.14.47-.14.73v2c0 1.1.9 2 2 2h6.31l-.95 4.57-.03.32c0 .41.17.79.44 1.06L9.83 23l6.59-6.59c.36-.36.58-.86.58-1.41V5c0-1.1-.9-2-2-2zm4 0v12h4V3h-4z"/></svg>{{ post.num_dislikes }}</span></InfoTooltip>
          </div>
        </div>
      </div>
      <div v-if="!posts.length" class="text-xs text-mist-slate text-center py-8">No posts available</div>
    </div>
  </div>
</template>

<script setup>
import InfoTooltip from '../InfoTooltip.vue'

defineProps({ posts: { type: Array, default: () => [] } })
</script>
