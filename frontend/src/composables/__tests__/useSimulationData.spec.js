import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import { useSimulationData } from '../useSimulationData.js'

describe('useSimulationData — new structured fields', () => {
  const makeJob = (structured) => ref({
    result_structured: JSON.stringify(structured),
    result_chat_log: '[]',
  })

  it('exposes verdict from structured', () => {
    const { verdict } = useSimulationData(makeJob({
      verdict: 'Unlikely to pass.',
      findings: [], stakeholder_positions: [], named_coalitions: [],
      phase_boundaries: [], quotable_posts: [], sim_scale: {},
      disagreement_axis: '', brief: '',
    }))
    expect(verdict.value).toBe('Unlikely to pass.')
  })

  it('exposes stakeholderPositions', () => {
    const { stakeholderPositions } = useSimulationData(makeJob({
      verdict: '', findings: [],
      stakeholder_positions: [{ name: 'Bloc A', stance: 'opposed', members: ['X'], member_count: 1, rationale_keywords: [] }],
      named_coalitions: [], phase_boundaries: [], quotable_posts: [],
      sim_scale: {}, disagreement_axis: '', brief: '',
    }))
    expect(stakeholderPositions.value).toHaveLength(1)
    expect(stakeholderPositions.value[0].stance).toBe('opposed')
  })

  it('exposes simScale', () => {
    const { simScale } = useSimulationData(makeJob({
      verdict: '', findings: [], stakeholder_positions: [], named_coalitions: [],
      phase_boundaries: [], quotable_posts: [],
      sim_scale: { participants: 10, horizon_days: 30, bloc_count: 2, market_stress: 'none_observed' },
      disagreement_axis: '', brief: '',
    }))
    expect(simScale.value.participants).toBe(10)
    expect(simScale.value.market_stress).toBe('none_observed')
  })

  it('no longer exposes sentimentBars', () => {
    const api = useSimulationData(makeJob({
      verdict: '', findings: [], stakeholder_positions: [], named_coalitions: [],
      phase_boundaries: [], quotable_posts: [], sim_scale: {},
      disagreement_axis: '', brief: '',
    }))
    expect(api.sentimentBars).toBeUndefined()
  })
})
