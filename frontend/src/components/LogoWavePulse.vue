<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 48 48"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    class="block"
  >
    <defs>
      <linearGradient :id="gradId" x1="0" y1="24" x2="48" y2="24">
        <stop offset="0%" stop-color="#22D3EE" />
        <stop offset="50%" stop-color="#A78BFA" />
        <stop offset="100%" stop-color="#FF6B6B" />
      </linearGradient>
    </defs>

    <!-- Concentric pulse rings -->
    <template v-if="animated">
      <circle cx="24" cy="24" r="20" stroke="#22D3EE" stroke-width="1" fill="none" opacity="0.12">
        <animate attributeName="r" values="16;22;16" dur="4s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.15;0.05;0.15" dur="4s" repeatCount="indefinite" />
      </circle>
      <circle cx="24" cy="24" r="14" stroke="#A78BFA" stroke-width="1" fill="none" opacity="0.15">
        <animate attributeName="r" values="12;17;12" dur="4s" begin="1.3s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.2;0.06;0.2" dur="4s" begin="1.3s" repeatCount="indefinite" />
      </circle>
      <circle cx="24" cy="24" r="8" stroke="#FF6B6B" stroke-width="1" fill="none" opacity="0.2">
        <animate attributeName="r" values="8;12;8" dur="4s" begin="2.6s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.25;0.08;0.25" dur="4s" begin="2.6s" repeatCount="indefinite" />
      </circle>
    </template>
    <template v-else>
      <circle cx="24" cy="24" r="16" stroke="#22D3EE" stroke-width="1.5" fill="none" opacity="0.15" />
      <circle cx="24" cy="24" r="10" stroke="#A78BFA" stroke-width="1.5" fill="none" opacity="0.2" />
    </template>

    <!-- Agent dots -->
    <template v-if="animated">
      <circle cx="10" cy="16" r="2" fill="#22D3EE" opacity="0.7">
        <animate attributeName="opacity" values="0.5;1;0.5" dur="3s" repeatCount="indefinite" />
      </circle>
      <circle cx="38" cy="18" r="1.5" fill="#A78BFA" opacity="0.6">
        <animate attributeName="opacity" values="0.5;1;0.5" dur="3s" begin="0.5s" repeatCount="indefinite" />
      </circle>
      <circle cx="14" cy="36" r="1.5" fill="#6EE7B7" opacity="0.6">
        <animate attributeName="opacity" values="0.5;1;0.5" dur="3s" begin="1s" repeatCount="indefinite" />
      </circle>
      <circle cx="36" cy="34" r="2" fill="#FF6B6B" opacity="0.7">
        <animate attributeName="opacity" values="0.5;1;0.5" dur="3s" begin="1.5s" repeatCount="indefinite" />
      </circle>
      <circle cx="24" cy="8" r="1.5" fill="#FBBF24" opacity="0.5">
        <animate attributeName="opacity" values="0.3;0.8;0.3" dur="3s" begin="2s" repeatCount="indefinite" />
      </circle>
    </template>
    <template v-else>
      <circle cx="12" cy="18" r="2" fill="#22D3EE" opacity="0.4" />
      <circle cx="36" cy="30" r="2" fill="#FF6B6B" opacity="0.4" />
    </template>

    <!-- Core -->
    <circle cx="24" cy="24" r="5" :fill="`url(#${gradId})`" opacity="0.9" />
    <circle cx="24" cy="24" r="2.5" fill="#F1F5F9" opacity="0.85" />
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: { type: Number, default: 36 },
  animated: { type: Boolean, default: true },
})

const gradId = computed(() => `logo-grad-${props.size}`)
</script>
