<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-3">Agent Profiles</div>
    <div class="grid grid-cols-2 lg:grid-cols-3 gap-3">
      <div v-for="(profile, i) in profiles" :key="i"
        class="bg-ocean-abyss border border-mist-depth rounded-xl p-3">
        <div class="text-sm font-medium text-mist-foam truncate">{{ profile.name || profile.user_name || 'Agent' }}</div>
        <div v-if="profile.persona || profile.bio" class="text-[11px] text-mist-slate mt-1 line-clamp-3">
          {{ profile.persona || profile.bio }}
        </div>
        <div class="flex gap-2 mt-2 text-[10px] text-mist-slate">
          <InfoTooltip v-if="profile.mbti" copyKey="agentProfileCards.mbti"><span class="px-1.5 py-0.5 bg-ocean-deep rounded">{{ profile.mbti }}</span></InfoTooltip>
          <span v-if="profile.country" class="px-1.5 py-0.5 bg-ocean-deep rounded">{{ profile.country }}</span>
        </div>
      </div>
      <div v-if="!profiles.length" class="col-span-full text-xs text-mist-slate text-center py-8">No profiles available</div>
    </div>
  </div>
</template>

<script setup>
import InfoTooltip from '../InfoTooltip.vue'

defineProps({ profiles: { type: Array, default: () => [] } })
</script>
