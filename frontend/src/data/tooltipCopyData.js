/** Tooltip copy for Data View components. */
export const dataTooltips = {
  // ── MarketCurveChart ──
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
  // ── EngagementChart ──
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
  // ── AgentTrajectoryChart ──
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
  // ── TopPostsFeed ──
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
  // ── TradeFeed ──
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
  // ── AgentProfileCards ──
  'agentProfileCards.mbti': {
    title: 'Personality Type',
    meaning: 'The agent\'s simulated personality using the MBTI framework. This shapes how the agent processes information, makes decisions, and interacts with others.',
    calculation: 'Assigned during agent creation based on the persona configuration. Influences posting style, risk tolerance, and social behavior.',
  },
  // ── SocialGraphView ──
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
}
