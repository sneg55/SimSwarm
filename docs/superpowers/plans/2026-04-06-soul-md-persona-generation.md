# Soul.md-Style Structured Persona Generation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure agent persona generation to use soul.md-inspired structured sections (SOUL + STYLE + BEHAVIOR) instead of freeform text, and fix the zero-engagement problem by rebalancing agent system prompts.

**Architecture:** The `persona` field remains a plain string, but its content changes from freeform prose to markdown-structured sections. This is invisible to downstream code — `to_twitter_format()`, `to_reddit_format()`, and the Wonderwall prompt builders all consume persona as opaque text. The generic per-platform style injection (`TWITTER_STYLE`/`REDDIT_STYLE` appended post-generation) is removed because per-agent STYLE sections now cover platform behavior. Engagement prompts in `prompts.py` are rebalanced to break the cold-start loop where agents never interact.

**Tech Stack:** Python (prompt engineering in MiroShark engine), no new dependencies.

**Issue:** [sneg55/SimSwarm#65](https://github.com/sneg55/SimSwarm/issues/65)

**Scope:** Phase 1 only (structured prompts + engagement fixes). Phase 2 (deep personas for protagonists) and Phase 3 (round-to-round memory) are separate plans.

**Testing note:** These changes are prompt engineering — the "test" is qualitative (do agents produce more distinctive, engaging output?). The tasks below include structural validation (prompt contains expected headers, removed code is gone) but the real validation is running a simulation end-to-end.

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `vendor/miroshark/backend/app/services/oasis_profile_generator.py` | Restructure persona prompts (lines 792-880) and rule-based fallback (lines 882-953) |
| Modify | `vendor/miroshark/backend/wonderwall/simulations/social_media/prompts.py` | Rebalance engagement defaults in Twitter + Reddit prompt builders |
| Modify | `infra/docker/simulation.py` | Remove `_patch_platform_profiles()` function |
| Modify | `infra/docker/constants.py` | Remove `TWITTER_STYLE` and `REDDIT_STYLE` constants |
| Modify | `infra/docker/run_job.py` | Remove the patching call |

No new files created. All changes are modifications to existing files.

---

### Task 1: Restructure Individual Persona Prompt

**Files:**
- Modify: `vendor/miroshark/backend/app/services/oasis_profile_generator.py:792-834`

- [ ] **Step 1: Replace `_build_individual_persona_prompt` method**

Replace the method at lines 792-834 with structured SOUL + STYLE + BEHAVIOR output format. The JSON schema stays identical (`bio`, `persona`, `age`, `gender`, `mbti`, `country`, `profession`, `interested_topics`) — only the instructions for `persona` content change.

```python
    def _build_individual_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """Build detailed persona prompt for individual entities using soul.md structure"""

        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "None"
        context_str = context[:3000] if context else "No additional context"

        return f"""Create a persona for this person to use in a multi-platform social media simulation.

ENTITY: {entity_name} ({entity_type})
SUMMARY: {entity_summary}
ATTRIBUTES: {attrs_str}

CONTEXT (from knowledge graph and research):
{context_str}

Return JSON with these fields:

"bio": A punchy social media bio (2-3 sentences). Not a resume — a vibe. What would this person actually write in their Twitter/Reddit bio? Include their attitude, not just their job title.

"persona": A structured character specification (800-1200 words total) using EXACTLY these three sections with markdown headers:

## SOUL (Identity & Worldview)
Write this person's core identity and belief system. Include:
- Background that shaped their worldview (not just resume facts — what experiences made them think the way they do?)
- 2-3 specific, defensible opinions on the simulation topic. Be concrete: not "supports regulation" but "believes self-regulation failed because of [specific reason], points to [specific evidence]"
- At least one named contradiction: "believes X but also Y" — real people hold contradictory views. Example: "champions free markets but quietly supports agricultural subsidies because they grew up on a farm"
- What would change their mind — what specific evidence or argument could shift their position? Or name the topic where they are genuinely unmovable and why

## STYLE (Voice & Writing Patterns)
Define how this person writes — distinctively enough that you could identify them from an anonymous post. Include:
- Sentence structure: short punchy fragments? long flowing paragraphs? rhetorical questions?
- Punctuation habits: em dashes, ellipses, ALL CAPS for emphasis, lowercase everything, excessive exclamation marks?
- Tone: sarcastic, earnest, dry, combative, professorial, folksy, techno-optimist?
- Vocabulary level: academic jargon, plain spoken, internet slang, industry buzzwords?
- Platform-specific patterns: On Twitter — do they thread or one-liner? On Reddit — do they write essays or quick takes? Do they use data/links or argue from personal experience?
- Rhetorical patterns: do they steel-man opponents? do they dunk? do they hedge? do they use analogies or go straight to data?

## BEHAVIOR (Operating Modes)
Define how this person acts on social media — their engagement personality:
- Post frequency tendency: prolific poster or occasional commenter?
- Engagement style: reply-heavy (loves arguing in threads) vs. broadcast (posts takes, rarely engages replies) vs. lurker-who-occasionally-erupts
- What triggers them to engage: do they respond to controversy? agreement? questions? misinformation? personal attacks?
- How they handle disagreement: block, mute, argue back, write a 20-tweet thread, get sarcastic, go quiet?
- Cross-platform behavior: how do they shift between Twitter (punchy), Reddit (detailed), and prediction markets (analytical)?

KEY PRINCIPLE: Someone reading the SOUL section should be able to predict this person's take on a NEW topic. If they can't, you're being too vague.

"age": Integer
"gender": "male" or "female"
"mbti": MBTI type (e.g., "INTJ")
"country": Country name
"profession": Their job title or role
"interested_topics": ["topic1", "topic2", ...] (3-6 topics)

IMPORTANT: Do NOT include karma, friend_count, follower_count, or statuses_count — those are computed separately.
"""
```

- [ ] **Step 2: Verify the change doesn't break JSON parsing**

The LLM is instructed to return JSON with `"persona"` as a string field. The markdown headers (`## SOUL`, etc.) live inside that string value. Verify by reading the `_generate_profile_with_llm` method (lines 605-680) — it parses the result as JSON and validates `bio` and `persona` fields exist. No change needed there since `persona` is still a string.

Run: `grep -n 'json.loads\|"persona"\|"bio"' vendor/miroshark/backend/app/services/oasis_profile_generator.py`

Expected: Lines 650, 653-656 show JSON parsing and field validation — no changes needed.

- [ ] **Step 3: Commit**

```bash
git add vendor/miroshark/backend/app/services/oasis_profile_generator.py
git commit -m "feat: restructure individual persona prompt to soul.md SOUL+STYLE+BEHAVIOR format

Replaces freeform 'persona' generation with structured sections:
- SOUL: identity, specific opinions, named contradictions
- STYLE: per-agent writing patterns and platform-specific voice
- BEHAVIOR: engagement patterns, triggers, cross-platform modes

Part of sneg55/SimSwarm#65"
```

---

### Task 2: Restructure Group/Institutional Persona Prompt

**Files:**
- Modify: `vendor/miroshark/backend/app/services/oasis_profile_generator.py:836-880`

- [ ] **Step 1: Replace `_build_group_persona_prompt` method**

Replace the method at lines 836-880. Organizations get the same three-section structure but with institutional framing.

```python
    def _build_group_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """Build detailed persona prompt for group/institutional entities using soul.md structure"""

        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "None"
        context_str = context[:3000] if context else "No additional context"

        return f"""Create an official social media account persona for this organization, for use in a multi-platform simulation.

ENTITY: {entity_name} ({entity_type})
SUMMARY: {entity_summary}
ATTRIBUTES: {attrs_str}

CONTEXT (from knowledge graph and research):
{context_str}

Return JSON with these fields:

"bio": The official account bio (2-3 sentences). Professional but not boring. Think real organizational Twitter bios — they have personality within institutional constraints.

"persona": A structured communications playbook (600-900 words total) using EXACTLY these three sections with markdown headers:

## SOUL (Institutional Identity & Position)
Define what this organization stands for and how it sees the world:
- Public mission and the image it projects — what does it want people to think of it?
- Official position on the simulation topic: what's the party line? How do they frame it?
- Institutional contradictions: what tension exists between stated values and actual behavior? Example: "champions transparency but routinely delays FOIA responses" or "promotes innovation but has a deeply risk-averse legal team"
- Red lines: what will this account NEVER say or do? What positions are off-brand?

## STYLE (Voice & Tone)
Define the account's distinctive communication style:
- Register: formal/accessible? Jargon-heavy or plain language?
- Person: first person plural ("we believe") or third person ("the organization maintains")?
- Personality: does it show personality or stay buttoned-up? Does it use humor? Emoji? Exclamation marks?
- Platform-specific patterns: On Twitter — press release tone or conversational? Does it use threads? On Reddit — does it do AMAs, post data, or just broadcast?
- Engagement voice: does it respond to critics? With what tone — dismissive, measured, empathetic?

## BEHAVIOR (Operating Modes)
Define how the account operates across platforms:
- Content strategy: what does it actually post? Press releases, data visualizations, opinion pieces, event promotion, community engagement?
- Engagement patterns: does it engage in debates or just broadcast? Does it reply to individual users or only to other institutions?
- Controversy handling: ignore, deflect, address head-on, or issue carefully worded non-responses?
- Frequency and timing: prolific daily poster or occasional announcements?
- Cross-platform behavior: same voice everywhere or adapted per platform (formal on Twitter, engaged on Reddit)?

"age": 30
"gender": "other"
"mbti": MBTI type reflecting the account's communication style. VARY THIS — not all orgs are ISTJ. \
Examples: "ISTJ" (conservative, by-the-book), "ENTJ" (assertive, agenda-setting), "ENFJ" (community-building, outreach), \
"INTP" (technical, research-focused), "ESTP" (bold, action-oriented)
"country": Country where headquartered
"profession": Brief description of institutional function
"interested_topics": ["topic1", "topic2", ...] (3-6 focus areas)

IMPORTANT: Do NOT include karma, friend_count, follower_count, or statuses_count — those are computed separately.
"""
```

- [ ] **Step 2: Commit**

```bash
git add vendor/miroshark/backend/app/services/oasis_profile_generator.py
git commit -m "feat: restructure group persona prompt to soul.md format

Institutional accounts now get structured SOUL+STYLE+BEHAVIOR sections
with institutional framing: mission, contradictions, red lines,
controversy handling, content strategy.

Part of sneg55/SimSwarm#65"
```

---

### Task 3: Update Rule-Based Fallback Personas

**Files:**
- Modify: `vendor/miroshark/backend/app/services/oasis_profile_generator.py:882-953`

The rule-based fallback generates flat persona strings when LLM fails. Update these to use the structured format so agents are consistent regardless of generation method.

- [ ] **Step 1: Replace `_generate_profile_rule_based` method**

```python
    def _generate_profile_rule_based(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate basic persona using rules, with structured soul.md sections"""

        entity_type_lower = entity_type.lower()
        summary_text = entity_summary or f"{entity_name} is a {entity_type.lower()}."

        if entity_type_lower in ["student", "alumni"]:
            persona = (
                f"## SOUL (Identity & Worldview)\n"
                f"{entity_name} is a {entity_type.lower()} engaged in academic and social discussions. "
                f"They tend to see issues through the lens of fairness and personal impact. "
                f"They hold strong opinions but are open to changing their mind when presented with data.\n\n"
                f"## STYLE (Voice & Writing Patterns)\n"
                f"Writes informally with occasional internet slang. Uses rhetorical questions. "
                f"On Twitter, posts quick reactions. On Reddit, writes 2-3 paragraph responses "
                f"drawing on personal experience.\n\n"
                f"## BEHAVIOR (Operating Modes)\n"
                f"Engagement-heavy — likes and comments frequently. Responds to controversy "
                f"and personal stories. Shares articles with brief commentary. "
                f"More active on Reddit than Twitter."
            )
            return {
                "bio": f"{entity_type} with interests in academics and social issues.",
                "persona": persona,
                "age": random.randint(18, 30),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": "Student",
                "interested_topics": ["Education", "Social Issues", "Technology"],
            }

        elif entity_type_lower in ["publicfigure", "expert", "faculty"]:
            persona = (
                f"## SOUL (Identity & Worldview)\n"
                f"{entity_name} is a recognized {entity_type.lower()} who has built authority "
                f"through years of domain expertise. They argue from evidence and professional "
                f"experience. {summary_text}\n\n"
                f"## STYLE (Voice & Writing Patterns)\n"
                f"Writes in a measured, authoritative tone. Uses data and citations. "
                f"On Twitter, posts concise takes with links. On Reddit, writes detailed "
                f"analytical responses. Avoids slang but isn't stuffy.\n\n"
                f"## BEHAVIOR (Operating Modes)\n"
                f"Moderate engagement — posts original takes and responds to substantive "
                f"challenges. Ignores trolls. Will correct misinformation in their domain. "
                f"Shares and comments on others' work in their field."
            )
            return {
                "bio": f"Expert and thought leader in their field.",
                "persona": persona,
                "age": random.randint(35, 60),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(["ENTJ", "INTJ", "ENTP", "INTP"]),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_attributes.get("occupation", "Expert"),
                "interested_topics": ["Politics", "Economics", "Culture & Society"],
            }

        elif entity_type_lower in ["mediaoutlet", "socialmediaplatform"]:
            persona = (
                f"## SOUL (Institutional Identity & Position)\n"
                f"{entity_name} is a media entity that reports news and facilitates public "
                f"discourse. Projects an image of objectivity and authority. "
                f"Will not take explicit partisan positions but has editorial leanings.\n\n"
                f"## STYLE (Voice & Tone)\n"
                f"Formal but accessible. Uses third person. Headlines are punchy, body text "
                f"is measured. On Twitter, posts headlines with links. On Reddit, posts "
                f"detailed article summaries.\n\n"
                f"## BEHAVIOR (Operating Modes)\n"
                f"High-frequency broadcaster. Posts breaking news, analysis, and opinion pieces. "
                f"Rarely engages in debates but will post corrections. "
                f"Responds to major controversies with official statements."
            )
            return {
                "bio": f"Official account for {entity_name}. News and updates.",
                "persona": persona,
                "age": 30,
                "gender": "other",
                "mbti": "ISTJ",
                "country": entity_attributes.get("country", "United States"),
                "profession": "Media",
                "interested_topics": ["General News", "Current Events", "Public Affairs"],
            }

        elif entity_type_lower in ["university", "governmentagency", "ngo", "organization"]:
            persona = (
                f"## SOUL (Institutional Identity & Position)\n"
                f"{entity_name} communicates official positions and engages with stakeholders. "
                f"Projects competence and public service. {summary_text}\n\n"
                f"## STYLE (Voice & Tone)\n"
                f"Professional and measured. Uses 'we' and formal language. "
                f"On Twitter, posts announcements and policy updates. On Reddit, "
                f"participates in relevant discussions with official perspective.\n\n"
                f"## BEHAVIOR (Operating Modes)\n"
                f"Moderate posting frequency. Broadcasts announcements and responds to "
                f"direct questions. Deflects controversy with careful language. "
                f"Engages more on Reddit than Twitter."
            )
            return {
                "bio": f"Official account of {entity_name}.",
                "persona": persona,
                "age": 30,
                "gender": "other",
                "mbti": "ISTJ",
                "country": entity_attributes.get("country", "United States"),
                "profession": entity_type,
                "interested_topics": ["Public Policy", "Community", "Official Announcements"],
            }

        else:
            persona = (
                f"## SOUL (Identity & Worldview)\n"
                f"{summary_text} Has opinions shaped by personal experience and "
                f"engages with topics they care about.\n\n"
                f"## STYLE (Voice & Writing Patterns)\n"
                f"Conversational tone. Writes naturally without heavy jargon. "
                f"On Twitter, posts brief takes. On Reddit, writes moderate-length "
                f"comments with personal perspective.\n\n"
                f"## BEHAVIOR (Operating Modes)\n"
                f"Moderately active — engages when topics are relevant to their interests. "
                f"Likes and comments on content they agree with. "
                f"Will push back on takes they disagree with but avoids flame wars."
            )
            return {
                "bio": entity_summary[:500] if entity_summary else f"{entity_type}: {entity_name}",
                "persona": persona,
                "age": random.randint(25, 50),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_type,
                "interested_topics": ["General", "Social Issues"],
            }
```

- [ ] **Step 2: Commit**

```bash
git add vendor/miroshark/backend/app/services/oasis_profile_generator.py
git commit -m "feat: update rule-based fallback personas to structured format

Fallback personas (used when LLM generation fails) now output the same
SOUL+STYLE+BEHAVIOR markdown structure as LLM-generated ones.

Part of sneg55/SimSwarm#65"
```

---

### Task 4: Remove Generic Platform Style Injection

**Files:**
- Modify: `infra/docker/constants.py:12-27` — remove `TWITTER_STYLE` and `REDDIT_STYLE`
- Modify: `infra/docker/simulation.py:1-82` — remove `_patch_platform_profiles()` and its import
- Modify: `infra/docker/run_job.py:69-73` — remove the patching call

The per-agent STYLE section in the persona now covers platform behavior, making the generic post-hoc injection redundant and counterproductive (it would append duplicate/conflicting instructions).

- [ ] **Step 1: Remove style constants from `constants.py`**

In `infra/docker/constants.py`, delete lines 8-27 (the comment block and both `TWITTER_STYLE` and `REDDIT_STYLE` constants). Keep `VLLM_URL`, `MIROSHARK_BACKEND`, and everything from `POSITIVE_WORDS` onward.

The file should go from:

```python
VLLM_URL = "http://localhost:8000/v1"
MIROSHARK_BACKEND = "/app/miroshark/backend"

# ---------------------------------------------------------------------------
# Platform-specific profile style instructions
# ---------------------------------------------------------------------------

TWITTER_STYLE = (
    "\n\nPLATFORM BEHAVIOR (Twitter): You are posting on Twitter. "
    ...
)

REDDIT_STYLE = (
    "\n\nPLATFORM BEHAVIOR (Reddit): You are posting on Reddit. "
    ...
)

# ---------------------------------------------------------------------------
# Sentiment word sets
# ---------------------------------------------------------------------------
```

To:

```python
VLLM_URL = "http://localhost:8000/v1"
MIROSHARK_BACKEND = "/app/miroshark/backend"

# ---------------------------------------------------------------------------
# Sentiment word sets
# ---------------------------------------------------------------------------
```

- [ ] **Step 2: Remove `_patch_platform_profiles()` from `simulation.py`**

In `infra/docker/simulation.py`:
1. Remove the import of `TWITTER_STYLE, REDDIT_STYLE` from the imports (line 11)
2. Remove the entire `_patch_platform_profiles()` function (lines 48-81)

The `csv` and `json` imports can also be removed since they were only used by the patching function. The file should contain only `prepare_simulation()` and `run_and_wait()`.

Updated imports:

```python
"""
Simulation preparation and execution.
"""
from __future__ import annotations

import os
import time
```

- [ ] **Step 3: Remove the patching call from `run_job.py`**

In `infra/docker/run_job.py`, remove lines 69-73:

```python
        # Patch profiles with platform-specific style
        try:
            _patch_platform_profiles(simulation_id)
        except Exception as exc:
            print(f"[run_job] WARNING: platform profile patching failed: {exc}", flush=True)
```

Also remove the import of `_patch_platform_profiles` from `simulation` (it's imported alongside `prepare_simulation` and `run_and_wait`). Check the exact import line and remove only `_patch_platform_profiles`.

- [ ] **Step 4: Verify no other references to removed code**

Run:
```bash
grep -rn "TWITTER_STYLE\|REDDIT_STYLE\|_patch_platform_profiles" infra/docker/
```

Expected: No matches.

- [ ] **Step 5: Commit**

```bash
git add infra/docker/constants.py infra/docker/simulation.py infra/docker/run_job.py
git commit -m "refactor: remove generic platform style injection

Per-agent STYLE sections in the structured persona now handle platform
behavior, replacing the generic TWITTER_STYLE/REDDIT_STYLE that was
appended post-generation. This eliminates duplicate/conflicting
instructions and gives each agent a distinctive voice per platform.

Part of sneg55/SimSwarm#65"
```

---

### Task 5: Rebalance Engagement Prompts

**Files:**
- Modify: `vendor/miroshark/backend/wonderwall/simulations/social_media/prompts.py:41-193`

The current prompts heavily discourage engagement ("do_nothing is YOUR DEFAULT", "90% lurking"), creating a cold-start problem where agents never interact. Rebalance to encourage natural engagement without spamming.

- [ ] **Step 1: Update `TwitterPromptBuilder.build_system_prompt`**

Replace lines 59-66 (the "HOW TO DECIDE" section) in the Twitter prompt. The key changes:
- Remove "90% of content" language
- Reframe do_nothing as one option among equals, not the overwhelmingly default
- Add guidance that agents should engage with at least some content per round

Replace:
```python
# HOW TO DECIDE WHAT TO DO
Read your feed carefully. Your DEFAULT action is **do_nothing** — you must \
have a specific reason to do anything else. Ask yourself: "Would I actually \
stop scrolling to engage with this?" If the answer isn't an immediate yes, \
call do_nothing.

1. **do_nothing** — YOUR DEFAULT. Call this unless one of the conditions \
below is clearly met. Real users scroll past 90% of content without engaging.
```

With:
```python
# HOW TO DECIDE WHAT TO DO
Read your feed carefully. For each post, ask yourself: "Would I actually \
stop scrolling to engage with this?" Act on your genuine reaction.

1. **do_nothing** — Skip content that doesn't interest you or provoke a \
reaction. Not everything deserves a response — but don't be a ghost either. \
Real users engage with content that hits their interests or triggers an emotion.
```

- [ ] **Step 2: Update `RedditPromptBuilder.build_system_prompt`**

Replace lines 139-146 (the "HOW TO DECIDE" section) in the Reddit prompt. Same philosophy — remove the "90% lurker" default.

Replace:
```python
# HOW TO DECIDE WHAT TO DO
Read the posts in your feed. Your DEFAULT action is **do_nothing** — you \
must have a specific reason to do anything else. Most Redditors are lurkers. \
Ask yourself: "Do I actually have something worth saying here?" If not, \
call do_nothing.

1. **do_nothing** — YOUR DEFAULT. Call this unless one of the conditions \
below is clearly met. Real Redditors lurk 90% of the time.
```

With:
```python
# HOW TO DECIDE WHAT TO DO
Read the posts in your feed. Ask yourself: "Do I have something worth \
saying here?" If a post touches your expertise, opinions, or experiences, \
engage with it.

1. **do_nothing** — Skip posts outside your interests or where you have \
nothing to add. But don't lurk through everything — if a discussion is \
relevant to you, join it. Upvote good content even if you don't comment.
```

- [ ] **Step 3: Commit**

```bash
git add vendor/miroshark/backend/wonderwall/simulations/social_media/prompts.py
git commit -m "fix: rebalance engagement prompts to break cold-start loop

Remove '90% lurking' defaults that caused zero agent engagement.
Agents now engage with content that matches their interests instead
of defaulting to inaction. do_nothing remains an option but is no
longer framed as the overwhelming default.

Fixes the zero-engagement problem documented in sneg55/SimSwarm#65"
```

---

### Task 6: Verify System Prompt Integration

**Files:**
- Read: `vendor/miroshark/backend/wonderwall/simulations/social_media/prompts.py:23-38`
- Read: `vendor/miroshark/backend/wonderwall/simulations/base.py`

This is a verification task — no code changes. Confirm that the structured persona (with `## SOUL`, `## STYLE`, `## BEHAVIOR` headers) will render correctly in the agent's final system prompt.

- [ ] **Step 1: Trace persona injection path**

The persona string flows through:
1. `OasisAgentProfile.persona` → `to_twitter_format()` puts it in `"persona"` key (or `to_reddit_format()`)
2. Profile CSV/JSON is loaded by Wonderwall into `user_info.profile["other_info"]["user_profile"]`
3. `_build_description(user_info)` in `prompts.py` (line 23-38) extracts `user_profile` and injects it as `"Your have profile: {user_profile}."`
4. This gets embedded in the system prompt returned by `build_system_prompt()`

Verify that `_build_description` does NOT truncate, escape, or strip markdown from the persona text. Read the function:

```python
def _build_description(user_info) -> str:
    """Extract name + profile description from user_info."""
    name_string = ""
    description_string = ""
    if user_info.name is not None:
        name_string = f"Your name is {user_info.name}."
    if user_info.profile is None:
        return name_string
    if "other_info" not in user_info.profile:
        return name_string
    if "user_profile" in user_info.profile["other_info"]:
        user_profile = user_info.profile["other_info"]["user_profile"]
        if user_profile is not None:
            description_string = f"Your have profile: {user_profile}."
            return f"{name_string}\n{description_string}"
    return name_string
```

Confirmed: it passes the full persona string through without modification. The `## SOUL`, `## STYLE`, `## BEHAVIOR` headers will render in the system prompt, giving the LLM clear section boundaries to attend to.

- [ ] **Step 2: Verify Twitter profile format**

Check `to_twitter_format()` (line 91-119 in `oasis_profile_generator.py`). The `persona` field is stored as `user_char` in the CSV. Verify the CSV writer doesn't strip markdown. The current `_patch_platform_profiles` uses `csv.writer` which correctly escapes multi-line strings. The `persona` field will contain newlines and `#` characters — CSV handles this fine as long as the value is quoted (which Python's `csv.writer` does automatically).

- [ ] **Step 3: No commit needed — verification only**

---

### Task 7: End-to-End Smoke Test

This task validates the full pipeline with a real simulation run.

- [ ] **Step 1: Build the worker Docker image**

```bash
cd infra/docker && docker build -t miroshark-worker:soul-md .
```

Verify the build succeeds without import errors (the removed `_patch_platform_profiles` import would fail here if not cleaned up correctly).

- [ ] **Step 2: Run a short simulation**

Run a simulation with `max_rounds=3` using a simple seed text. Inspect the generated profiles:

```bash
# After profile generation, check the twitter_profiles.csv
# Look for ## SOUL, ## STYLE, ## BEHAVIOR headers in the user_char column

# Check reddit_profiles.json  
# Look for structured sections in the persona field
```

- [ ] **Step 3: Verify agent engagement**

In the simulation output, check that agents are actually engaging with each other's content:
- `num_likes > 0` on at least some posts
- `num_comments > 0` on at least some posts  
- Agents are creating comments, not just original posts

- [ ] **Step 4: Verify voice differentiation**

Read the chat log and check that agents have distinct writing styles — different sentence lengths, different tones, different engagement patterns. Compare 2-3 agents' posts to confirm they don't all sound the same.

---

## Summary of Changes

| Change | Impact | Risk |
|--------|--------|------|
| Structured persona prompt (individual) | High — every individual agent gets distinctive SOUL+STYLE+BEHAVIOR | Low — same JSON schema, same field names |
| Structured persona prompt (group) | Medium — institutional accounts get richer operating playbook | Low — same as above |
| Rule-based fallback update | Low — only triggers when LLM fails (rare) | Low — same field structure |
| Remove platform style injection | Medium — eliminates generic style that made agents sound similar | Low — per-agent STYLE section replaces it |
| Rebalance engagement prompts | High — directly fixes zero-engagement problem | Medium — may over-correct; tune thresholds if agents become too chatty |

## Out of Scope (Future Plans)

- **Phase 2: Deep Personas for Protagonists** — Two-call generation for high graph-degree entities using enrichment data for style extraction
- **Phase 3: Round-to-Round Memory** — Per-agent memory accumulation across simulation rounds
- **Engagement seeding** — Seeding first-round posts with initial likes to bootstrap engagement
- **Recsys novelty bonus** — Adding novelty scoring to recommendation system to surface new content
