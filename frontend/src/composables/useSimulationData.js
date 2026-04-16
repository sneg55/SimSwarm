import { computed } from 'vue'

export function useSimulationData(job) {
  const chatLog = computed(() => {
    if (!job.value) return []
    try {
      const raw = job.value.result_chat_log || job.value.chat_log || '[]'
      const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
      return Array.isArray(parsed) ? parsed : []
    } catch { return [] }
  })

  const chatMessages = computed(() => {
    return chatLog.value
      .map(entry => {
        if (entry.content && entry.role) return entry
        const args = entry.action_args || {}
        const body = args.text ?? args.content ?? entry.content
        return {
          role: 'assistant',
          agent: entry.agent_name || entry.agent || 'Agent',
          content: body ?? JSON.stringify(args),
          timestamp: entry.timestamp || null,
        }
      })
      .filter(m => m.content)
  })

  const structured = computed(() => {
    const raw = job.value?.result_structured ?? job.value?.structured ?? null
    if (!raw) return null
    try {
      const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)
          && Object.keys(parsed).length === 0) {
        return null
      }
      return parsed
    } catch { return null }
  })

  // New Path 3 / Path 2 fields — all lift straight out of structured
  const verdict = computed(() => structured.value?.verdict || '')
  const stakeholderPositions = computed(() => structured.value?.stakeholder_positions || [])
  const namedCoalitions = computed(() => structured.value?.named_coalitions || [])
  const phaseBoundaries = computed(() => structured.value?.phase_boundaries || [])
  const quotablePosts = computed(() => structured.value?.quotable_posts || [])
  const simScale = computed(() => structured.value?.sim_scale || {})
  const disagreementAxis = computed(() => structured.value?.disagreement_axis || '')

  function buildNodeRelationships(nodes, edges) {
    const nameMap = Object.fromEntries(nodes.map(n => [n.uuid, n.name || n.uuid]))
    const relMap = {}
    for (const edge of edges) {
      const src = edge.source_node_uuid
      const tgt = edge.target_node_uuid
      if (!relMap[src]) relMap[src] = []
      if (!relMap[tgt]) relMap[tgt] = []
      relMap[src].push({
        direction: 'outgoing',
        target_uuid: tgt,
        targetName: edge.target_node_name || nameMap[tgt] || tgt,
        type: edge.name || edge.fact || '',
        fact: edge.fact || '',
      })
      relMap[tgt].push({
        direction: 'incoming',
        source_uuid: src,
        sourceName: edge.source_node_name || nameMap[src] || src,
        type: edge.name || edge.fact || '',
        fact: edge.fact || '',
      })
    }
    return nodes.map(n => ({ ...n, relationships: relMap[n.uuid] || [] }))
  }

  return {
    chatLog, chatMessages, structured,
    verdict, stakeholderPositions, namedCoalitions,
    phaseBoundaries, quotablePosts, simScale, disagreementAxis,
    buildNodeRelationships,
  }
}
