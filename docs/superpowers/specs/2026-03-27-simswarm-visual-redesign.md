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

## 4. Dashboard (Minimal Launchpad)

Keep it simple — the value is in the results, not the dashboard.

- **Header**: "Dashboard" heading + Credit Badge (navbar already has it too)
- **Primary action**: Large "New Simulation" button, coral gradient CTA style, prominent center placement
- **Credit warning**: Yellow/amber callout banner when balance < 30, links to Account
- **Recent simulations**: List of simulation cards (dark card style from component system)
  - Each shows: goal text, tier badge, timestamp, status badge (completed/running/pending/failed)
  - Status colors: Completed=cyan, Running=violet+breathing, Pending=slate, Failed=coral
  - Hover: top-edge glow, title shifts to cyan, "View Results" or "View Progress" link
- **Empty state**: "No simulations yet" with illustration suggestion and link to create first
- Dark background throughout (Abyss base)

## 5. New Simulation: Stepped Wizard

3-step guided flow with organic transitions between steps.

### Step 1 — "Let's seed the ecosystem..."
- Drag-and-drop document upload zone (Abyss bg, dashed Teal border)
- File type tags below (Press release, Policy draft, Earnings report, Campaign brief)
- Textarea fallback for direct text input
- Supported formats: PDF, TXT, CSV, Markdown, up to 50,000 characters
- Upload shows gentle schooling particles gathering animation

### Step 2 — "What do you want to know?"
- Single textarea for research goal
- Smart prompt suggestions below as clickable tags:
  - "How will the market react to..."
  - "What will public sentiment be if..."
  - "How will stakeholders respond to..."
- Faint water-surface reflection effect on textarea (subtle)

### Step 3 — "Choose your ecosystem size"
- Tier selector (3 cards with unique accent colors)
- Cost calculator showing credit cost for selected tier
- Credit warning if insufficient balance
- "Run Simulation" primary CTA button
- Pre-filled tier recommendation based on document length

### Wizard UX
- Progress indicator: 3 connected dots with flowing current line between them
- Smooth slide transition between steps (page "ripples" forward)
- Background gradient shifts gently between steps
- "Quick Start" option for repeat users (after first 2-3 runs): compact single-page view
- Progress saver: resumes where user left off if tab is closed
- "Save as draft" link visible throughout

## 6. Simulation Results: Guided Story (Default)

The flagship experience — a scrollable narrative that weaves the graph into the report.

### Layout
- Single continuous scroll, no mode switching by default
- Tiny toggle in top-right corner for power users: "Story" | "Graph" | "Report"
- Soft flowing timeline on the side (current lines) showing scroll progress

### Scroll Sections
1. **Executive brief** — Clean narrative summary at the top. Key findings in plain language.
2. **Key findings** — Each finding is a card with colored accent border. As user scrolls to a finding, the knowledge graph (embedded inline) animates to highlight the relevant agent cluster.
3. **Sentiment analysis** — Opinion gradients visualized as flowing color bands. Agent clusters glow and drift as user scrolls.
4. **Coalition map** — Graph visualization showing which agent groups converged. Organic node layout, bioluminescent glow on active clusters.
5. **Confidence scores** — JetBrains Mono data readout. Clean metrics presentation.
6. **Full report** — Complete markdown-rendered report with prose styling.
7. **Agent chat replay** — Collapsible chat log showing agent interactions chronologically.

### Scroll-Driven Animation
- Fluid, water-like scroll behavior (gentle momentum)
- As user scrolls through each finding, the knowledge graph responds:
  - Relevant agent clusters gently glow and drift together
  - Connection lines brighten between interacting agents
  - Subtle particle flows pulse when narrative calls attention
- Smooth morphing charts that feel alive (not snapping)
- Graph fades in organically as user scrolls past the executive brief

### Export
- Sticky "Export" button: PDF (server-side), JSON, CSV
- PDF captures the guided story with static graph snapshots

### Mobile
- Graph becomes a mini-map on smaller screens
- Dual column mode disabled below 768px
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
