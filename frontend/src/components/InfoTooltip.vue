<template>
  <span
    ref="triggerRef"
    data-testid="tooltip-trigger"
    class="inline-flex items-center gap-0.5 relative"
    @mouseenter="onTriggerEnter"
    @mouseleave="onTriggerLeave"
  >
    <slot />
    <svg
      v-if="tooltip"
      data-testid="info-icon"
      role="button"
      tabindex="0"
      aria-label="More info"
      :class="iconSize === 'md' ? 'w-4 h-4' : 'w-3 h-3'"
      class="shrink-0 text-teal-400/50 hover:text-teal-300 transition-colors cursor-help"
      viewBox="0 0 20 20"
      fill="currentColor"
      @keydown.enter.prevent="toggleTooltip"
      @keydown.space.prevent="toggleTooltip"
      @focus="onTriggerEnter"
      @blur="onTriggerLeave"
    >
      <path
        fill-rule="evenodd"
        d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0
           1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25
           0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747
           15H11a.75.75 0 000-1.5h-.253a.25.25 0
           01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
        clip-rule="evenodd"
      />
    </svg>
    <Teleport to="body" :disabled="teleportDisabled">
      <Transition
        :name="noMotion ? '' : 'tooltip-fade'"
        @before-enter="transHooks.onBeforeEnter"
        @enter="transHooks.onEnter"
        @leave="transHooks.onLeave"
      >
        <div
          v-if="visible"
          ref="panelRef"
          data-testid="tooltip-panel"
          role="tooltip"
          class="fixed z-[9999] max-w-[280px] rounded-lg px-3.5 py-3"
          :style="computedPanelStyle"
          @mouseenter="onPanelEnter"
          @mouseleave="onPanelLeave"
        >
          <div class="absolute w-1.5 h-1.5 rotate-45" :style="arrowStyles[actualPosition]" />
          <div class="text-teal-300 text-[10px] font-semibold uppercase tracking-wider mb-1">
            {{ tooltip.title }}
          </div>
          <div class="text-gray-200 text-sm leading-relaxed">
            {{ tooltip.meaning }}
          </div>
          <div class="mt-2 pt-2" :style="dividerStyle">
            <span :style="{ color: calcLabelColor }" class="text-xs">Calculated from: </span>
            <span class="text-gray-400 text-xs leading-relaxed">{{ tooltip.calculation }}</span>
          </div>
        </div>
      </Transition>
    </Teleport>
  </span>
</template>

<script setup>
import { computed, ref } from 'vue'
import { getTooltip } from '../data/tooltipCopy.js'
import {
  useTooltipPosition,
  tooltipTransitionHooks,
  reducedMotion,
} from '../composables/useTooltipPosition.js'
import {
  arrowStyles,
  panelBaseStyle,
  dividerStyle,
  calcLabelColor,
} from './tooltipArrowStyles.js'

const props = defineProps({
  copyKey: { type: String, required: true },
  position: { type: String, default: 'top' },
  iconSize: { type: String, default: 'sm' },
})

// Disable Teleport in test environments so wrapper.find can traverse the panel
const teleportDisabled = typeof __vitest_browser__ !== 'undefined'
  || (typeof process !== 'undefined' && process.env?.NODE_ENV === 'test')
  || (typeof navigator !== 'undefined' && navigator.userAgent?.includes('jsdom'))

const tooltip = computed(() => getTooltip(props.copyKey))
const noMotion = reducedMotion
const transHooks = tooltipTransitionHooks()
const triggerRef = ref(null)

const {
  visible, panelRef, panelPos, actualPosition,
  onTriggerEnter, onTriggerLeave, onPanelEnter, onPanelLeave,
  toggleTooltip,
} = useTooltipPosition(computed(() => !!tooltip.value), props.position, triggerRef)

const computedPanelStyle = computed(() => ({
  ...panelBaseStyle,
  top: `${panelPos.value.top}px`,
  left: `${panelPos.value.left}px`,
}))
</script>
