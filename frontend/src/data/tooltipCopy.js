/**
 * Central tooltip copy dictionary.
 * Key format: camelCaseComponentName.camelCaseMetricName
 * Each entry: { title, meaning, calculation }
 */
export const tooltipCopy = {
  // ── Story View: ConfidenceGrid ──
  'confidenceGrid.agentsActive': {
    title: 'Agents Active',
    meaning: 'The number of simulated agents that participated in this scenario. Each agent has its own personality, knowledge, and goals.',
    calculation: 'Counted from the total agents that posted, traded, or interacted at least once during the simulation.',
  },
  'confidenceGrid.roundsCompleted': {
    title: 'Rounds Completed',
    meaning: 'How many cycles the simulation ran. Each round represents a period where all agents can act — post, trade, react, and update their beliefs.',
    calculation: 'One round completes when every active agent has had a chance to act. The number depends on the tier and complexity of your scenario.',
  },
  'confidenceGrid.totalInteractions': {
    title: 'Total Interactions',
    meaning: 'The combined number of actions agents took — posts, likes, comments, trades, and follows. Higher numbers mean a more active simulated community.',
    calculation: 'Sum of every discrete action across all agents and all rounds.',
  },
  // ── Story View: SentimentBars ──
  'sentimentBars.overallSentiment': {
    title: 'Overall Sentiment',
    meaning: 'The general emotional tone across all agents by the end of the simulation. Positive means the community leaned favorable; negative means skeptical or opposed.',
    calculation: 'Averaged from each agent\'s final sentiment score, which updates every round based on what they read, post, and experience.',
  },
  'sentimentBars.consensus': {
    title: 'Consensus',
    meaning: 'How much agents agreed with each other by the end. High consensus means a dominant shared view emerged; low means opinions stayed divided.',
    calculation: 'Measured from the spread of final agent positions — tighter clustering means higher consensus.',
  },
  'sentimentBars.volatility': {
    title: 'Volatility',
    meaning: 'How much opinions shifted during the simulation. High volatility means agents frequently changed their minds; low means positions were stable early.',
    calculation: 'Tracked from round-to-round sentiment changes across all agents, then averaged.',
  },
  'sentimentBars.engagement': {
    title: 'Engagement',
    meaning: 'How actively agents participated relative to opportunities. High engagement means agents chose to post and interact rather than stay silent.',
    calculation: 'Ratio of actions agents actually took versus the maximum possible actions across all rounds.',
  },
  // ── Story View: CoalitionCard ──
  'coalitionCard.agents': {
    title: 'Coalition Members',
    meaning: 'How many agents belong to this group. Coalitions form naturally when agents with similar views start interacting and reinforcing each other.',
    calculation: 'Counted from agents the simulation identified as behaviorally clustered — they share stances, interact frequently, and reference similar ideas.',
  },
  'coalitionCard.strength': {
    title: 'Coalition Strength',
    meaning: 'How tightly aligned this group is. A high percentage means members consistently agree with each other and act in coordination.',
    calculation: 'Measured from how often coalition members take the same stance and interact with each other versus with outsiders, across all rounds.',
  },
  // ── Story View: FindingCard ──
  'findingCard.metric': {
    title: 'Finding Metric',
    meaning: 'A standout number that captures the scale or impact of this finding.',
    calculation: 'Derived from the specific pattern described — may reflect engagement multiples, sentiment shifts, or adoption rates depending on the finding.',
  },
  // ── Story View: EngagementCompact ──
  'engagementCompact.totalPosts': {
    title: 'Total Posts',
    meaning: 'The total number of original posts agents published across all rounds. Posts are how agents share their views and influence others.',
    calculation: 'Sum of all CREATE_POST actions by every agent across every round.',
  },
  'engagementCompact.totalLikes': {
    title: 'Total Likes',
    meaning: 'How many times agents endorsed each other\'s content. Likes signal agreement and amplify a post\'s reach within the simulation.',
    calculation: 'Sum of all LIKE_POST actions across every agent and round.',
  },
  // ── Story View: MarketCurveCompact ──
  'marketCurveCompact.currentYes': {
    title: 'Current YES Probability',
    meaning: 'The market\'s latest estimate that the predicted outcome will happen. Think of it like a crowd-sourced confidence level — agents bet real simulation credits on what they believe.',
    calculation: 'Derived from the last trade price. When agents buy YES shares, the price rises; when they sell, it falls. The percentage reflects the balance of conviction.',
  },
  // ── Story View: SimulationResults header ──
  'simulationResults.tier': {
    title: 'Simulation Tier',
    meaning: 'The complexity level of this run. Higher tiers use more agents, more rounds, and more capable AI models — producing richer and more nuanced results.',
    calculation: 'Set when the simulation was created. Each tier defines agent count, round count, context window, and GPU allocation.',
  },
  'simulationResults.startedAt': {
    title: 'Started',
    meaning: 'When the simulation began processing on the GPU.',
    calculation: 'Recorded when the job was picked up by a GPU worker.',
  },
  'simulationResults.completedAt': {
    title: 'Completed',
    meaning: 'When the simulation finished and results became available.',
    calculation: 'Recorded when the final round completes and all data is extracted and stored.',
  },
  // ── Data View: MarketCurveChart ──
  'marketCurveChart.currentPrice': {
    title: 'Current Price',
    meaning: 'The latest market probability for this outcome.',
    calculation: 'Last trade price in the market\'s order book.',
  },
  'marketCurveChart.tooltipYes': {
    title: 'YES Price',
    meaning: 'What the market thinks is the probability this outcome happens.',
    calculation: 'Set by the last trade — when an agent buys YES shares, the price moves up.',
  },
  'marketCurveChart.tooltipNo': {
    title: 'NO Price',
    meaning: 'The implied probability this outcome does not happen.',
    calculation: 'Calculated as 100% minus the YES price. Always moves inversely.',
  },
  'marketCurveChart.tooltipVolume': {
    title: 'Trade Volume',
    meaning: 'Total simulation currency spent on this trade. Larger trades signal stronger conviction from the agent.',
    calculation: 'The dollar cost the agent paid for the shares in this transaction.',
  },
  'marketCurveChart.hoverMeaning': {
    title: 'Trade',
    meaning: 'Each trade shifts the price based on how much an agent is willing to pay for their predicted outcome.',
    calculation: 'Price moves with each buy or sell order from simulation agents.',
  },
  // ── Data View: EngagementChart ──
  'engagementChart.posts': {
    title: 'Posts This Round',
    meaning: 'Original content published by agents during this round.',
    calculation: 'Count of CREATE_POST actions in this specific round.',
  },
  'engagementChart.likes': {
    title: 'Likes This Round',
    meaning: 'Endorsements agents gave to each other\'s content this round.',
    calculation: 'Count of LIKE_POST and LIKE_COMMENT actions in this round.',
  },
  'engagementChart.comments': {
    title: 'Comments This Round',
    meaning: 'Replies and reactions agents wrote on each other\'s posts.',
    calculation: 'Count of CREATE_COMMENT actions in this round.',
  },
  'engagementChart.activeAgents': {
    title: 'Active Agents',
    meaning: 'How many agents did something this round — posted, liked, commented, or traded. Idle agents stayed quiet.',
    calculation: 'Count of distinct agents with at least one action in this round.',
  },
  'engagementChart.hoverMeaning': {
    title: 'Round Activity',
    meaning: 'What happened during this simulation cycle — all agent posts, reactions, and social interactions for the round.',
    calculation: 'Aggregated from all agent actions recorded in this round.',
  },
  // ── Data View: AgentTrajectoryChart ──
  'agentTrajectoryChart.sentiment': {
    title: 'Agent Sentiment',
    meaning: 'This agent\'s emotional position at this point in the simulation. +1 is fully supportive, -1 is fully opposed, 0 is neutral.',
    calculation: 'Updated each round based on what the agent posted, read, and how others responded to them. Reflects cumulative belief evolution.',
  },
  'agentTrajectoryChart.hoverMeaning': {
    title: 'Agent Position',
    meaning: 'How this agent\'s opinion evolved through the simulation based on their posts, interactions, and the content they consumed.',
    calculation: 'Tracked from round-to-round changes in the agent\'s expressed sentiment.',
  },
  // ── Data View: TopPostsFeed ──
  'topPostsFeed.likes': {
    title: 'Likes',
    meaning: 'How many other agents endorsed this post. Popular posts shape the conversation and pull sentiment toward them.',
    calculation: 'Count of LIKE_POST actions targeting this specific post.',
  },
  'topPostsFeed.shares': {
    title: 'Shares',
    meaning: 'How many agents amplified this post to their followers. Shares extend a post\'s reach beyond the original audience.',
    calculation: 'Count of REPOST and QUOTE_POST actions targeting this post.',
  },
  'topPostsFeed.dislikes': {
    title: 'Dislikes',
    meaning: 'How many agents actively disagreed with this post. Dislikes signal opposition and can dampen a post\'s influence.',
    calculation: 'Count of DISLIKE_POST actions targeting this post.',
  },
  // ── Data View: TradeFeed ──
  'tradeFeed.price': {
    title: 'Trade Price',
    meaning: 'The probability level at which this agent bought or sold. A BUY at 70% means the agent believes there\'s at least a 70% chance the outcome happens.',
    calculation: 'The market price at the moment this trade executed.',
  },
  'tradeFeed.cost': {
    title: 'Trade Cost',
    meaning: 'How much simulation currency the agent spent on this position. Larger bets mean the agent had stronger conviction.',
    calculation: 'Calculated from share quantity multiplied by price. Reflects the agent\'s resource commitment.',
  },
  // ── Data View: AgentProfileCards ──
  'agentProfileCards.mbti': {
    title: 'Personality Type',
    meaning: 'The agent\'s simulated personality using the MBTI framework. This shapes how the agent processes information, makes decisions, and interacts with others.',
    calculation: 'Assigned during agent creation based on the persona configuration. Influences posting style, risk tolerance, and social behavior.',
  },
  // ── Data View: SocialGraphView ──
  'socialGraphView.nodeSize': {
    title: 'Node Size',
    meaning: 'Larger nodes represent agents with more followers. These agents have more social influence in the simulation.',
    calculation: 'Scaled from each agent\'s follower count using a square root scale for readability.',
  },
  'socialGraphView.mutualEdge': {
    title: 'Bright Edges',
    meaning: 'A bright connection means both agents follow each other — a mutual relationship. These tend to be the strongest influence channels.',
    calculation: 'Detected when agent A follows agent B and agent B follows agent A.',
  },
  // ── Graph View: GraphLegend ──
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
  // ── Graph View: GraphDetailPanel ──
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
  // ── Graph View: GraphVisualization hover tooltip ──
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

export function normalizeKey(label) {
  if (!label || !label.trim()) return ''
  const words = label.trim().split(/\s+/)
  return words
    .map((w, i) => i === 0
      ? w[0].toLowerCase() + w.slice(1).toLowerCase()
      : w[0].toUpperCase() + w.slice(1).toLowerCase())
    .join('')
}

export function getTooltip(key) {
  return tooltipCopy[key] || null
}
