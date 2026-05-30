/**
 * Central tooltip copy — aggregates per-view dictionaries.
 * Key format: camelCaseComponentName.camelCaseMetricName
 */
import { storyTooltips } from './tooltipCopyStory.js'
import { dataTooltips } from './tooltipCopyData.js'
import { graphTooltips } from './tooltipCopyGraph.js'

export const tooltipCopy = {
  ...storyTooltips,
  ...dataTooltips,
  ...graphTooltips,
}

/**
 * Convert a display label to a camelCase dictionary key.
 * "Agents Active" → "agentsActive", "Graph Entities" → "graphEntities"
 */
export function normalizeKey(label) {
  if (!label || !label.trim()) return ''
  const words = label.trim().split(/\s+/)
  return words
    .map((w, i) => i === 0
      ? w[0].toLowerCase() + w.slice(1).toLowerCase()
      : w[0].toUpperCase() + w.slice(1).toLowerCase())
    .join('')
}

/** Look up a tooltip entry by key. Returns null if not found. */
export function getTooltip(key) {
  return tooltipCopy[key] || null
}
