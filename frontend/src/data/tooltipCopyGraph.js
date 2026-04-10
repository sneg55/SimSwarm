/** Tooltip copy for Graph View components. */
export const graphTooltips = {
  // ── GraphLegend ──
  'graphLegend.entityCount': {
    title: 'Entity Count',
    meaning: 'How many knowledge graph nodes belong to this type. The graph captures people, organizations, concepts, and events the simulation discovered.',
    calculation: 'Counted from all nodes extracted from agent conversations and enrichment data, filtered by this entity type.',
  },
  'graphLegend.sentimentPositive': {
    title: 'Positive Sentiment',
    meaning: 'Nodes the simulation community viewed favorably — they were discussed in supportive or optimistic terms.',
    calculation: 'Nodes with a final averaged sentiment score above +0.2.',
  },
  'graphLegend.sentimentNegative': {
    title: 'Negative Sentiment',
    meaning: 'Nodes the community viewed unfavorably — discussed with skepticism, criticism, or opposition.',
    calculation: 'Nodes with a final averaged sentiment score below -0.2.',
  },
  'graphLegend.sentimentNeutral': {
    title: 'Neutral Sentiment',
    meaning: 'Nodes discussed without strong positive or negative feeling — factual references or divided opinions that balanced out.',
    calculation: 'Nodes with a final averaged sentiment score between -0.2 and +0.2.',
  },
  // ── GraphDetailPanel ──
  'graphDetailPanel.connectionCount': {
    title: 'Connections',
    meaning: 'How many other entities in the knowledge graph are linked to this one. More connections means this entity was referenced in more contexts.',
    calculation: 'Count of all incoming and outgoing relationships for this node.',
  },
  'graphDetailPanel.sentiment': {
    title: 'Sentiment',
    meaning: 'The community\'s overall feeling toward this entity. Positive values mean favorable discussion; negative means critical or opposed.',
    calculation: 'Averaged from sentiment scores across all agent mentions and interactions involving this entity.',
  },
  'graphDetailPanel.stance': {
    title: 'Stance',
    meaning: 'The dominant community position on this entity — supportive, opposing, or observer.',
    calculation: 'Derived from the balance of positive vs negative interactions. Supportive if sentiment > +0.2, opposing if < -0.2, observer otherwise.',
  },
  'graphDetailPanel.influenceWeight': {
    title: 'Influence Weight',
    meaning: 'How much this entity affected the simulation\'s narrative. Higher multipliers mean this entity was central to how opinions formed and spread.',
    calculation: 'Calculated from connection count, mention frequency, and the sentiment intensity of interactions involving this entity.',
  },
  'graphDetailPanel.roundNumber': {
    title: 'Round',
    meaning: 'Which simulation cycle this activity happened in. Earlier rounds show initial reactions; later rounds show evolved positions.',
    calculation: 'The sequential round number when this specific action was recorded.',
  },
  // ── GraphVisualization hover tooltip ──
  'graphVisualization.hoverSentiment': {
    title: 'Sentiment',
    meaning: 'How the simulated community feels about this entity.',
    calculation: 'Averaged from all agent mentions — positive means supportive discussion, negative means critical.',
  },
  'graphVisualization.hoverStance': {
    title: 'Stance',
    meaning: 'The community\'s dominant position toward this entity.',
    calculation: 'Classified from the sentiment score — supportive, opposing, or neutral observer.',
  },
  'graphVisualization.hoverMeaning': {
    title: 'Entity',
    meaning: 'A person, organization, concept, or event discovered during the simulation through agent conversations and web enrichment.',
    calculation: 'Extracted from agent discussions and enrichment data during the simulation run.',
  },
}
