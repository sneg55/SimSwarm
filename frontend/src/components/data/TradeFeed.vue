<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-3">Trades</div>
    <div class="space-y-1 max-h-[400px] overflow-y-auto">
      <div v-for="trade in trades" :key="trade.trade_id"
        class="flex items-center gap-3 p-2 rounded-lg hover:bg-ocean-abyss/50 transition-colors text-xs">
        <span :class="trade.side === 'buy' ? 'text-green-400' : 'text-red-400'" class="font-mono font-bold w-8">
          {{ trade.side === 'buy' ? 'BUY' : 'SELL' }}
        </span>
        <span class="text-ocean-cyan truncate flex-1">{{ trade.agent_name }}</span>
        <span class="text-mist-drift">{{ trade.outcome }}</span>
        <InfoTooltip copyKey="tradeFeed.price"><span class="text-mist-slate font-mono">@ {{ (trade.price * 100).toFixed(0) }}%</span></InfoTooltip>
        <InfoTooltip copyKey="tradeFeed.cost"><span class="text-mist-slate font-mono">${{ Math.round(trade.cost) }}</span></InfoTooltip>
      </div>
      <div v-if="!trades.length" class="text-xs text-mist-slate text-center py-8">No trades available</div>
    </div>
  </div>
</template>

<script setup>
import InfoTooltip from '../InfoTooltip.vue'

defineProps({ trades: { type: Array, default: () => [] } })
</script>
