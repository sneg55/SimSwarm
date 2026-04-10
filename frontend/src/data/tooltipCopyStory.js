/** Tooltip copy for Story View components. */
export const storyTooltips = {
  // ── ConfidenceGrid ──
  // Backend sends labels: "Agents", "Rounds", "Graph Entities", "Trades"
  'confidenceGrid.agents': {
    title: 'Agents',
    meaning: 'The number of simulated agents that participated in this scenario. Each agent has its own personality, knowledge, and goals.',
    calculation: 'Counted from the total agents that posted, traded, or interacted at least once during the simulation.',
  },
  'confidenceGrid.rounds': {
    title: 'Rounds',
    meaning: 'How many cycles the simulation ran. Each round represents a period where all agents can act — post, trade, react, and update their beliefs.',
    calculation: 'One round completes when every active agent has had a chance to act. The number depends on the tier and complexity of your scenario.',
  },
  'confidenceGrid.graphEntities': {
    title: 'Graph Entities',
    meaning: 'The number of people, organizations, concepts, and events discovered in the knowledge graph. The graph captures what agents discussed and how topics connect.',
    calculation: 'Counted from all nodes extracted from agent conversations and web enrichment data.',
  },
  'confidenceGrid.trades': {
    title: 'Trades',
    meaning: 'The total number of prediction market trades agents made. Each trade represents an agent putting simulation credits behind their belief about the outcome.',
    calculation: 'Counted from the polymarket simulation database — every buy and sell order across all markets.',
  },
  // ── SentimentBars ──
  // Backend sends platform names as labels: "Twitter", "Reddit", "Polymarket"
  'sentimentBars.twitter': {
    title: 'Twitter Sentiment',
    meaning: 'How positively agents behaved on the Twitter platform. Higher percentages mean more constructive actions like posting and liking versus passive or negative actions.',
    calculation: 'Percentage of positive actions (posts, likes, reposts, comments) out of all Twitter actions across the simulation.',
  },
  'sentimentBars.reddit': {
    title: 'Reddit Sentiment',
    meaning: 'How positively agents behaved on the Reddit platform. Higher percentages mean more constructive engagement.',
    calculation: 'Percentage of positive actions out of all Reddit actions across the simulation.',
  },
  'sentimentBars.polymarket': {
    title: 'Polymarket Sentiment',
    meaning: 'How actively agents traded in prediction markets. Lower values may indicate cautious or bearish sentiment — agents avoiding bets or selling positions.',
    calculation: 'Percentage of active trading actions (buys, sells) out of all prediction market interactions.',
  },
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
  // ── CoalitionCard ──
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
  // ── FindingCard ──
  'findingCard.metric': {
    title: 'Finding Metric',
    meaning: 'A standout number that captures the scale or impact of this finding.',
    calculation: 'Derived from the specific pattern described — may reflect engagement multiples, sentiment shifts, or adoption rates depending on the finding.',
  },
  // ── EngagementCompact ──
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
  // ── MarketCurveCompact ──
  'marketCurveCompact.currentYes': {
    title: 'Current YES Probability',
    meaning: 'The market\'s latest estimate that the predicted outcome will happen. Think of it like a crowd-sourced confidence level — agents bet real simulation credits on what they believe.',
    calculation: 'Derived from the last trade price. When agents buy YES shares, the price rises; when they sell, it falls. The percentage reflects the balance of conviction.',
  },
  // ── SimulationResults header ──
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
}
