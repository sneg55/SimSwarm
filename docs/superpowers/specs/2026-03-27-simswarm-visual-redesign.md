# SimSwarm Visual Identity & UI Redesign Spec

## 1. Brand Identity

### Name
**SimSwarm** — retained. The aquatic/organic visual language carries the "living systems" feel without requiring a literal name.

### Logo: Wave Pulse
Concentric ripple rings radiating from a gradient core, with agent dots scattered in the wave field. Communicates signal propagation and emergent spread.

- **Full mark**: 3 animated concentric rings (cyan → violet → coral) pulsing outward at staggered intervals. 5-6 agent dots at varying sizes/colors breathing around the rings. Central core: gradient fill (cyan→violet→coral) with bright white center.
- **Navbar**: 36×36px, animated rings + breathing dots. Scales up 10% and rotates 5° on hover.
- **Favicon**: Static simplified — 2 rings, core dot, 2 agent particles.
- **Footer**: Static simplified — 2 rings, core, 2 particles at lower opacity.

### Color Palette: "Deep Ocean"

**Primary — Ocean Depths:**
| Name | Hex | Usage |
|------|-----|-------|
| Abyss | `#0B1426` | Page backgrounds |
| Deep | `#0F2035` | Card surfaces |
| Teal | `#164E63` | Interactive surfaces, borders |
| Cyan | `#0E7490` | Primary actions, buttons |
| Bioluminescent | `#22D3EE` | Glows, highlights, active states |

**Accent — Coral Reef:**
| Name | Hex | Usage |
|------|-----|-------|
| Coral | `#FF6B6B` | CTAs, alerts, negative sentiment |
| Warm Amber | `#F97316` | Warnings, energy |
| Sand | `#FBBF24` | Highlights, badges, emerging trends |

**Organic — Living Systems:**
| Name | Hex | Usage |
|------|-----|-------|
| Sage | `#10B981` | Success, growth, completed states |
| Seafoam | `#6EE7B7` | Positive sentiment |
| Deep Violet | `#A78BFA` | AI/swarm identity |

**Neutrals — Ocean Mist:**
| Name | Hex | Usage |
|------|-----|-------|
| Foam | `#F1F5F9` | Primary text on dark |
| Mist | `#CBD5E1` | Body text |
| Drift | `#94A3B8` | Secondary text |
| Slate | `#64748B` | Tertiary text, metadata |
| Depth | `#1E293B` | Borders, dividers |

### Typography
- **Headings & Body**: Inter — clean, enterprise-ready, wide weight range
- **Data & Metrics**: JetBrains Mono — technical precision, agent counts, simulation IDs
- **Heading weights**: 800 (hero), 700 (section), 600 (card titles), 500 (labels)
- **Body**: 400 weight, 16px, line-height 1.7
- **Letter spacing**: -0.03em on hero, -0.02em on sections, -0.01em on card titles

### Micro-Interaction Principles
- **Easing**: `cubic-bezier(0.34, 1.56, 0.64, 1)` — slightly springy, like water tension releasing
- **Glow breathing**: 3s cycle on idle bioluminescent elements
- **Hover lifts**: 2-6px translateY with shadow increase
- **Active press**: Brief scale(0.97) compression
- **Button light**: Radial gradient follows cursor position via CSS custom properties
- **Button ripple**: Expanding circle from click point, 0.6s fade
- **Focus rings**: 3px outer glow in cyan with 0.15 opacity spread
- **Transitions**: Never snap — everything flows with 0.25-0.5s durations

### Bioluminescent Node System
Agent visualization uses colored glowing nodes with semantic meaning:
- **Cyan** (#22D3EE): Active agent / neutral
- **Coral** (#FF6B6B): Negative sentiment
- **Seafoam** (#6EE7B7): Positive sentiment / cluster
- **Deep Violet** (#A78BFA): AI synthesis
- **Sand** (#FBBF24): Emerging trend
- Nodes pulse at staggered phases, hover pauses animation and enlarges 25%

## 2. Component System

### Buttons
- **Primary**: Gradient bg (cyan-600→cyan-500), white text, 16px glow shadow, radial light follow + ripple
- **Ghost**: Transparent bg, cyan text, teal border. Hover: teal fill at 20% opacity
- **CTA**: Gradient bg (coral→amber), white text, coral glow shadow. Reserved for main conversion actions.
- All buttons: 12px 24px padding, 10px border-radius, 15px font, 600 weight

### Cards (Simulation)
- Dark gradient bg (Abyss→Deep), 1px Depth border, 12px radius
- Top-edge bioluminescent line (2px, transparent→cyan→transparent) appears on hover
- Title shifts to cyan on hover, metadata brightens from Slate to Drift
- Status badge: pill shape, 20px radius, colored bg at 10% opacity + 1px border

### Form Inputs
- Abyss background, Depth border, 10px radius
- Focus: Cyan border + 3px outer glow + background shifts to slightly lighter
- Dropzone: 2px dashed Teal border, hover shifts to Cyan, drag-over adds inset glow + slight scale(1.01)
- Tags/chips: springy hover lift with teal highlight

### Tier Selector
- 3 cards, each with unique accent color (Cyan / Violet / Sand)
- Selected: accent border + radial glow from bottom + darker bg
- Hover: lift + border shift. Cost number scales 1.05 on hover
- Each tier's glow color matches its accent via CSS custom properties

### Pipeline Progress
- 5 steps: Seed → Research → Simulate → Analyze → Report
- Completed: green checkmark, Sage bg at 15%
- Active: Cyan pulsing glow (2.5s breathing), shimmer line on active connector
- Pending: Deep bg, Slate text
- All steps have hover tooltips that slide in from below

### Credit Badge
- Pill shape, inline flex, green (healthy) or coral (low < 30)
- Icon rotates 90° on hover
- Glow intensifies on hover

### Navbar
- Frosted glass: rgba(Abyss, 0.7) + backdrop-filter blur(20px)
- Shrinks padding on scroll (16→10px), bg opacity increases
- Links: underline grows from left on hover via pseudo-element
- Wave Pulse logo with animated rings

### Toast Notifications
- Springs up from bottom-right with springy easing
- Breathing cyan dot indicator
- Click to dismiss

## 3. Landing Page

### Structure (6 sections)

**1. Hero**
- Full viewport height, centered text
- Interactive canvas swarm background: 120 agents scattered uniformly
  - 5 invisible "attractors" wander the canvas and periodically activate (every 5-15s)
  - Active attractors pull nearby agents into temporary swirling clusters for 4-10 seconds
  - Agents have gentle sine-based organic drift + soft repulsion between each other
  - Connection lines appear between agents within 80px
  - Mouse cursor attracts agents within 200px radius
  - Subtle hint text: "Move your mouse to attract the swarm"
- Rotating headline: "What if you could watch [rotating word] form in real time?"
  - Words slide up from below, current word slides up and out
  - 2.5s interval, 0.6s transition with smooth cubic-bezier
  - Phrases: public opinion, market reactions, geopolitical shifts, crisis responses, cultural impacts, regulatory cascades, supply-chain ripples, stakeholder coalitions, sentiment waves, escalation paths, economic trajectories, narrative ecosystems
  - All words rendered with gradient text (cyan→violet→coral)
  - Wrapper fixed to widest word width (measured after font load) to prevent layout shift
- Subtitle: "Upload a document. Launch a swarm of AI agents..."
- CTAs: "Get started" (coral gradient) + "See it in action ↓" (ghost)
- Trust badges: "Pay-as-you-go credits" · "Results in under 5 minutes" · "Up to 10,000 agent swarms"
- Scroll progress bar at top: gradient line (cyan→violet) tracking scroll position

**2. Experience Story (How It Works)**
- Header: "Three steps. One living ecosystem."
- 3 alternating left/right steps, fade-in-on-scroll via IntersectionObserver:
  - **Step 01 — Seed the ecosystem**: Drop your document. Mockup shows drag-and-drop zone with floating icon + document type tags.
  - **Step 02 — Watch the swarm evolve**: Agents school and interact. Mockup shows animated swarm agents swimming in a canvas.
  - **Step 03 — Insights surface naturally**: Ecosystem reveals patterns. Mockup shows stacked insight cards with colored accent borders (coral = key finding, seafoam = coalition, violet = confidence).
- Each mockup has browser chrome (3 dots) and lifts on hover

**3. Social Proof**
- 3 testimonial cards from target personas (Head of Strategy, Policy Director, VP Comms)
- Cards lift on hover with border color shift

**4. Pricing**
- 3 credit pack cards: Starter ($19/100cr), Pro ($79/500cr), Heavy ($249/2000cr)
- Each card has unique accent color (cyan/violet/sand)
- Pro card is featured: darker gradient bg, "Most popular" badge, visible top accent line
- All "Get started" buttons have hover lift + shadow (not just featured)
- Feature list items have glowing accent-colored bullet dots

**5. Final CTA**
- Radial gradient background (teal + coral wash)
- "Ready to see what happens next?" + "Get started" coral button

**6. Footer**
- Simplified Wave Pulse logo + copyright
- Links: Privacy, Terms, Docs, GitHub

### Navigation
- Fixed side dots (right edge): 5 dots tracking current section, labels on hover
- Frosted glass navbar with smooth scroll links

## 4. Dashboard (Stacked Minimal Launchpad)

Two-zone layout: calm waterline strip on top, living simulation list below.

### Waterline Strip (Top Zone)
- 80-100px height, soft gradient background (Deep → Abyss), subtle radial teal wash
- **Left**: "Welcome back" greeting + credit balance ("342 credits remaining · 3 simulations this week")
- **Right**: Prominent "New Simulation" button — coral gradient CTA with + icon, flows into stepped wizard
- Credit warning integrates into the balance text (turns coral when < 30)

### Simulation List (Main Zone)
Two sections separated by subtle label dividers:

**Active simulations:**
- Cards show: title, goal (truncated), status with breathing purple dot, pipeline step ("Step 3/5 — Simulating"), tier + agent count, elapsed time
- Breathing status dot animates at 2.5s cycle

**Completed simulations (with key insight):**
- Cards show: title, **one-line key finding** (the star of the card), tier + agent count + duration + timestamp
- Key finding displayed in a subtle inset panel with colored accent bar:
  - Coral bar: negative sentiment shifts
  - Seafoam bar: positive findings
  - Sand bar: emerging trends/narratives
- `key_insight` field: pre-baked string (max ~100 chars) stored when simulation completes, pulled from the first key finding in the guided story results
- Backend: add `key_insight` column to job model, populate from results processor

**Failed simulations:**
- Show error reason in subdued text instead of insight ("GPU timeout — try a smaller tier")
- Coral status dot (static, no breathing)

### Card Interactions
- Hover: top-edge glow line (color matches status), title shifts to cyan, "View results →" link fades in
- Click anywhere: opens guided story results (completed) or progress page (running)
- Cards lift 2px on hover with subtle shadow

### Empty State
- Centered illustration: concentric pulse rings (from logo) with breathing agent dots
- Copy: "Your ecosystem is ready. What would you like to simulate today?"
- CTA: "Start your first simulation" button (ocean cyan gradient)

### Implementation Note
- Max 6-8 cards visible before "View all" link
- No charts, no analytics, no clutter — the value is in the results pages
- Dark background throughout (Abyss base)

## 5. New Simulation: Stepped Wizard

3-step guided flow, centered layout (max-w 640px), fade-slide transitions between steps.

### Progress Indicator
- 3 dots (Seed / Goal / Launch) connected by lines at the top
- Active dot: cyan glow, completed dots: green, pending: mist-depth border
- Active line: shimmer animation (gradient sweep), completed: solid green
- Dots are clickable to jump between completed steps

### Step 1 — "Let's seed the ecosystem"
Three input methods with uppercase section labels:

**DIRECT UPLOAD:**
- Drag-and-drop zone (dashed Teal border, 14px radius, compact padding)
- Floating wave icon, "Drop your document here" text
- "Browse files" button (teal outline, opens native file picker)
- Format line: `PDF, DOCX, TXT, Markdown — up to 50,000 characters` (JetBrains Mono, subdued)
- Drag-over state: cyan border + inset glow + slight scale
- After upload: shows file card with name, size, extracted character count, remove button

**IMPORT FROM SOURCE:**
- URL input with link icon + "Fetch" button (cyan gradient)
- Loading state → success message with extracted char count + hostname
- Fetched content populates the raw input textarea

**RAW INPUT:**
- Textarea (Abyss bg, mist-depth border, 90px min-height)
- Character counter: `0 / 50,000` (JetBrains Mono, right-aligned)

**"What makes a good seed?"** — collapsible tips panel between header and inputs:
- ✓ Specific events (earnings reports, policy announcements, product launches)
- ✓ Multiple stakeholders (companies, regulators, media, public figures)
- ✓ Recent context (last few days)
- ○ 2,000–20,000 characters sweet spot
- ✗ Avoid generic content (boilerplate, Wikipedia)

### Step 2 — "What do you want to know?"
- Large textarea (16px font, 140px min-height) for research question
- Smart prompt suggestions as clickable tags below:
  - "How will the market react to..."
  - "What will public sentiment be if..."
  - "How will stakeholders respond to..."
  - "What narrative will form around..."
  - "What coalitions will emerge after..."
- Clicking a suggestion fills the textarea and focuses it

### Step 3 — "Choose your ecosystem size"
**Tier selector** — 3 cards with unique accents (cyan/violet/sand):
- Each shows: tier name, agent range, credit cost, estimated duration
- Selected state: accent border + radial glow + darker bg
- Disabled state (insufficient credits): 40% opacity, cursor not-allowed

**Visual explainer** — "How size affects your simulation" panel:
- Three mini graph visualizations side by side with arrows:
  - Small: 5 dots, 2 edges → "Fewer perspectives · Faster results · Key trends only"
  - Medium: 10 dots, 5 edges → "Balanced depth · Coalition detection · Most popular choice"
  - Large: 17 dots, 10 edges → "Maximum diversity · Emergent coalitions · Deepest insights"
- Dots use entity type colors, edges are subtle connection lines

**Cost summary** card:
- Left: "Simulation cost" label + credit amount (JetBrains Mono, cyan) + "Balance after" (green)
- Right: Current balance display
- Credit warning (amber) if balance is low

**Launch button**: "Run Simulation" coral gradient CTA with rocket icon

### Navigation
- Back/Continue buttons at bottom of each step, separated by border-top
- Continue: cyan gradient button with arrow icon
- Back: ghost text button with back arrow
- Fade-slide animation between steps (0.5s ease-out)

## 6. Simulation Results (Three Views)

Three views of the same simulation data, accessible via a segmented toggle (Story | Graph | Report) in the top toolbar. All views share a consistent bottom action bar.

### Shared UI Elements

**Top toolbar** (frosted glass, below navbar):
- Left: breadcrumb (← Dashboard / Simulation title)
- Right: view toggle (Story | Graph | Report)

**Bottom action bar** (frosted glass, fixed bottom, centered):
- Story/Report tabs: `Export as PDF` | `Export as JSON` | `Export as CSV` | `Share simulation` (primary teal)
- Graph tab: `Export as PNG` | `Export as PDF` | `Share simulation` (primary teal)

**Simulation header** (shown in Story and Report views):
- Title, goal text, meta bar (tier, agent count, cluster count, rounds, duration, completion date)

### 6a. Story View (Default)

The guided story — a scrollable narrative that weaves the graph into the report.

**Side timeline** (left edge, fixed):
- Vertical dots tracking scroll position through sections
- Labels appear on hover, clickable to jump
- Active dot = cyan glow, passed dots = teal

**Scroll sections** (fade in via IntersectionObserver):
1. **Executive Brief** — Two-paragraph narrative in a card with cyan-highlighted key phrases
2. **Key Findings** — Cards with colored accent bars (coral = negative, seafoam = positive, violet = bifurcation, sand = emerging). Each has a metric badge (JetBrains Mono). After the first finding, an inline knowledge graph panel appears showing the relevant cluster highlighted.
3. **Sentiment Analysis** — Animated gradient bars that grow when scrolled into view. Per-cluster breakdown (institutional, retail, media, etc.)
4. **Coalition Map** — 4 cards showing emergent agent groups with colored dots, agent counts, and coalition strength percentages
5. **Confidence Scores** — Three big numbers in JetBrains Mono (Overall, Sentiment, Coalition stability)
6. **Full Report** — Prose section with markdown formatting
7. **Agent Chat Replay** — Collapsible, click to expand. Timestamped messages with color-coded agent names by role. System messages for round transitions.

**Inline graph panel** (between findings):
- Browser chrome header (title + icon controls: zoom, reset, fullscreen)
- Shows clustered nodes with the relevant cluster highlighted (brighter glow + stronger edges)

### 6b. Graph View

Full-viewport interactive knowledge graph.

**Top toolbar additions** (same row as view toggle):
- Zoom to fit, Reset layout (icon buttons)
- Type / Sentiment toggle (segmented control — rearranges nodes by entity type clusters or positive/neutral/negative sentiment clusters)
- Edge labels toggle (icon)
- Layout dropdown (Force-directed, Circle, Hierarchical, Grid)
- Export PNG, Fullscreen (icon buttons)

**Search bar** (left side of toolbar):
- Type to filter entities, dropdown shows results with colored type badges (ORG, GOV, PERSON)

**Legend** (bottom-left, floating):
- Entity type filter: colored dots + counts, click to toggle visibility (nodes fade to 8% opacity, edges disappear)
- All / None quick actions
- Sentiment filter: Positive (seafoam ring) / Negative (coral ring) / Neutral — same click-to-toggle behavior
- "Showing X of Y nodes" with "Show all" link

**Node rendering** (Canvas 2D):
- Nodes colored by entity type, sized by sentiment intensity (stronger conviction = up to 40% larger)
- Sentiment ring around each node: thickness and glow scale with intensity. Positive = seafoam, Negative = coral, Neutral = none
- Background sentiment zones: soft radial gradient blobs behind positive cluster (seafoam wash) and negative cluster (coral wash)
- Gentle organic drift (sine-based wandering), repulsion between nearby nodes
- Connection lines between related entities (0.5px, blended colors, 10% opacity)

**Click interactions:**
- Click node → detail panel slides in from right (320px), canvas area shrinks to accommodate
- Connected nodes light up with names visible, unconnected nodes dim to 15%
- Edges to/from selected node brighten and thicken
- Detail panel shows: type badge, entity name, summary, relationship list
- Click relationship in panel → target node gets ping animation (expanding rings for 3s) with name and edges highlighted
- Click empty canvas → close panel, everything returns to normal

**Grouping:**
- "Type" mode: nodes cluster by entity type (Organization, Person, Media, etc.)
- "Sentiment" mode: nodes rearrange into 3 groups (Positive left, Neutral center, Negative right), sub-grouped by entity type. Nodes flow to new positions over ~3s with stronger gravity during transition.

### 6c. Report View

Traditional full-text report with prose styling.

**Table of Contents** (left side, fixed):
- Tracks scroll position with active highlighting (cyan left border)
- Section headings + sub-headings, clickable to jump
- Hidden below 1200px viewport width

**Report body** (centered, max-width 760px, shifted right to accommodate left TOC):
- Dark card with 40px padding
- Typography: h1 (26px, border-bottom), h2 (20px), h3 (16px)
- Body text: 15px, line-height 1.8
- Inline metric badges: colored pills (positive = seafoam, negative = coral, neutral = cyan) with JetBrains Mono
- Blockquotes: teal left border, subtle teal background tint
- Tables: header with uppercase labels, hover row highlight
- Code: JetBrains Mono in cyan on teal tint
- Lists: teal markers
- HR: gradient line divider

**Agent Chat Replay** (below report, collapsible):
- Click header to expand/collapse
- Message count badge
- Color-coded agent names, timestamps, system messages for round transitions

### Mobile
- Graph becomes a mini-map on smaller screens
- Report TOC hidden below 1200px
- Scroll story works naturally on mobile (single column)

## 7. Design Tokens Summary (Tailwind Config)

```js
// tailwind.config.js theme.extend
colors: {
  ocean: {
    abyss: '#0B1426',
    deep: '#0F2035',
    teal: '#164E63',
    cyan: '#0E7490',
    glow: '#22D3EE',
  },
  coral: {
    DEFAULT: '#FF6B6B',
    amber: '#F97316',
    sand: '#FBBF24',
  },
  organic: {
    sage: '#10B981',
    seafoam: '#6EE7B7',
    violet: '#A78BFA',
  },
  mist: {
    foam: '#F1F5F9',
    DEFAULT: '#CBD5E1',
    drift: '#94A3B8',
    slate: '#64748B',
    depth: '#1E293B',
  },
},
fontFamily: {
  sans: ['Inter', ...defaultTheme.fontFamily.sans],
  mono: ['JetBrains Mono', ...defaultTheme.fontFamily.mono],
},
```

## 8. Tone & Copy Guidelines

- **Exploratory and calm**: "Watch the swarm evolve", "Let the digital ecosystem reveal patterns"
- **Premium without playful**: Never use exclamation marks in marketing copy. No emojis in UI (only in trust badges if needed).
- **Action-oriented**: "Get started", "Run Simulation", "View Results"
- **No "free" language**: The product is pay-as-you-go credits. Never say "free trial" or "start free."
- **Domain-aware**: Copy should resonate with strategists, analysts, PR teams — not developers. No technical jargon (no "API", "Docker", "GPU" in user-facing copy).

## 9. Target Audience Context

Primary users are non-technical domain experts: marketers, PR/crisis teams, corporate strategists, financial analysts, policymakers, product managers. They have high domain sophistication but low-medium technical sophistication. They expect Notion/Figma-level polish with zero friction.

- Pain tolerance for complexity: extremely low
- If the UI feels "developer-y" or requires any setup explanation, they bounce
- Results must be beautiful and shareable with stakeholders (C-suite consumption)
- The guided story format is the key differentiator for this audience

## 10. Implementation Scope

### Pages to redesign (in priority order):
1. Landing page (full rebuild)
2. Simulation Results (guided story — new default experience)
3. New Simulation (stepped wizard — new flow)
4. Dashboard (restyle with new design system)
5. Navbar (new logo + frosted glass)
6. Login / Register (restyle)
7. Account (restyle)
8. Demo Results (match new results format)

### New shared infrastructure:
- Tailwind theme extension with design tokens
- Inter + JetBrains Mono font loading
- Shared CSS utilities for glow effects, springy transitions
- Canvas swarm component (reusable for hero + status page)
- Wave Pulse logo SVG component

### Mockup reference:
Interactive mockups preserved at `.superpowers/brainstorm/` in the landing-page worktree.
