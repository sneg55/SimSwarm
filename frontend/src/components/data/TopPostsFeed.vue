<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-3">Top Posts</div>
    <div class="space-y-1 max-h-[400px] overflow-y-auto">
      <div v-for="post in posts" :key="post.post_id + post.platform"
        class="flex gap-3 p-3 rounded-xl hover:bg-ocean-abyss/50 transition-colors">
        <div class="flex-shrink-0 text-sm">{{ post.platform === 'twitter' ? '𝕏' : '📱' }}</div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2 mb-1">
            <span class="text-xs font-medium text-ocean-cyan truncate">{{ post.agent_name }}</span>
            <span class="text-[10px] text-mist-slate">{{ post.platform }}</span>
          </div>
          <p class="text-xs text-mist-drift leading-relaxed line-clamp-3">{{ post.content }}</p>
          <div class="flex gap-3 mt-1.5 text-[10px] text-mist-slate">
            <InfoTooltip v-if="post.num_likes" copyKey="topPostsFeed.likes"><span class="text-green-400">♥ {{ post.num_likes }}</span></InfoTooltip>
            <InfoTooltip v-if="post.num_shares" copyKey="topPostsFeed.shares"><span>↻ {{ post.num_shares }}</span></InfoTooltip>
            <InfoTooltip v-if="post.num_dislikes" copyKey="topPostsFeed.dislikes"><span class="text-red-400">↓ {{ post.num_dislikes }}</span></InfoTooltip>
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
