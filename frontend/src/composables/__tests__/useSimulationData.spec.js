import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import { useSimulationData } from '../useSimulationData.js'

describe('useSimulationData', () => {
  it('returns empty when job is null', () => {
    const job = ref(null)
    const { chatLog, chatMessages, structured, sentimentBars } = useSimulationData(job)
    expect(chatLog.value).toEqual([])
    expect(chatMessages.value).toEqual([])
    expect(structured.value).toBe(null)
    expect(sentimentBars.value).toEqual([])
  })

  it('parses chatLog from result_chat_log string', () => {
    const job = ref({ result_chat_log: JSON.stringify([
      { role: 'user', content: 'hi' },
      { agent_name: 'Bot', action_args: { content: 'hello' } },
    ]) })
    const { chatLog, chatMessages } = useSimulationData(job)
    expect(chatLog.value.length).toBe(2)
    expect(chatMessages.value[0].content).toBe('hi')
    expect(chatMessages.value[1].agent).toBe('Bot')
    expect(chatMessages.value[1].content).toBe('hello')
  })

  it('handles malformed JSON gracefully', () => {
    const job = ref({ result_chat_log: 'not json' })
    const { chatLog } = useSimulationData(job)
    expect(chatLog.value).toEqual([])
  })

  it('handles already-parsed chatLog array', () => {
    const job = ref({ chat_log: [{ role: 'user', content: 'x' }] })
    const { chatLog } = useSimulationData(job)
    expect(chatLog.value.length).toBe(1)
  })

  it('parses structured from string or object', () => {
    const job = ref({ result_structured: JSON.stringify({ foo: 'bar' }) })
    const { structured } = useSimulationData(job)
    expect(structured.value.foo).toBe('bar')

    const job2 = ref({ structured: { baz: 1 } })
    const { structured: s2 } = useSimulationData(job2)
    expect(s2.value.baz).toBe(1)
  })

  it('returns null for unparseable structured', () => {
    const job = ref({ result_structured: '{broken' })
    const { structured } = useSimulationData(job)
    expect(structured.value).toBe(null)
  })

  it('computes sentimentBars with positive/negative/zero', () => {
    const job = ref({ result_structured: { sentiment: [
      { label: 'Optimism', value: 60, direction: 'positive' },
      { label: 'Risk', value: 40, direction: 'negative' },
      { label: 'Unknown', value: 0, direction: 'positive' },
    ] } })
    const { sentimentBars } = useSimulationData(job)
    expect(sentimentBars.value.length).toBe(3)
    expect(sentimentBars.value[0].value).toBe('60%')
    expect(sentimentBars.value[2].value).toBe('N/A')
  })

  it('buildNodeRelationships constructs bidirectional relations', () => {
    const job = ref(null)
    const { buildNodeRelationships } = useSimulationData(job)
    const nodes = [
      { uuid: '1', name: 'A' },
      { uuid: '2', name: 'B' },
    ]
    const edges = [{ source_node_uuid: '1', target_node_uuid: '2', name: 'KNOWS', fact: 'knows' }]
    const result = buildNodeRelationships(nodes, edges)
    expect(result[0].relationships[0].direction).toBe('outgoing')
    expect(result[1].relationships[0].direction).toBe('incoming')
  })

  it('reads post body from action_args.text (native engine key)', () => {
    const job = ref({ result_chat_log: JSON.stringify([
      { agent_name: 'Alice', action_type: 'CREATE_POST', action_args: { text: 'hello world' } },
    ]) })
    const { chatMessages } = useSimulationData(job)
    expect(chatMessages.value[0].content).toBe('hello world')
  })

  it('prefers action_args.text over action_args.content when both present', () => {
    const job = ref({ result_chat_log: JSON.stringify([
      { agent_name: 'Alice', action_type: 'CREATE_POST',
        action_args: { text: 'from text', content: 'from content' } },
    ]) })
    const { chatMessages } = useSimulationData(job)
    expect(chatMessages.value[0].content).toBe('from text')
  })
})
