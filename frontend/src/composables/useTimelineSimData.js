import { ref, watch } from 'vue'
import { getSimData } from '../api/jobs.js'

/**
 * Loads the three JSON blobs (market curves, top posts, agent trajectories)
 * that the timeline band consumes, gated on job.sim_data_available.
 */
export function useTimelineSimData(job) {
  const marketCurves = ref([])
  const topPosts = ref([])
  const agentTrajectories = ref([])

  async function fetchJson(url) {
    if (!url) return null
    const resp = await fetch(url)
    return resp.ok ? resp.json() : null
  }

  async function load() {
    if (!job.value?.sim_data_available) return
    try {
      const { files } = await getSimData(job.value.id)
      const [mc, tp, at] = await Promise.all([
        fetchJson(files['market_curves.json']),
        fetchJson(files['top_posts.json']),
        fetchJson(files['agent_trajectories.json']),
      ])
      marketCurves.value = mc || []
      topPosts.value = tp || []
      agentTrajectories.value = at || []
    } catch (e) {
      console.error('Failed to load timeline sim-data:', e)
    }
  }

  watch(
    () => job.value?.sim_data_available,
    (v) => { if (v) load() },
    { immediate: true },
  )

  return { marketCurves, topPosts, agentTrajectories }
}

/**
 * Smooth-scroll to the DOM element referenced by a timeline moment and
 * briefly highlight it.
 */
export function scrollToMoment(moments, momentId) {
  const moment = (moments || []).find(m => m.id === momentId)
  if (!moment || !moment.refId) return
  const el = document.getElementById(moment.refId)
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  el.classList.add('ring-2', 'ring-ocean-glow')
  setTimeout(() => el.classList.remove('ring-2', 'ring-ocean-glow'), 1500)
}

/**
 * Infer the round count from market curves or agent trajectories.
 */
export function computeRoundCount(mc, at) {
  const fromMarkets = Math.max(
    0,
    ...((mc || []).flatMap(m => (m.points || []).map(p => p.round_num || 0))),
  )
  const fromAgents = Math.max(
    0,
    ...((at || []).flatMap(a => (a.stance_per_round || []).map(s => s.round_num || 0))),
  )
  return Math.max(fromMarkets, fromAgents)
}
