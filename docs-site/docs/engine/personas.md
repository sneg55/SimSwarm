---
sidebar_label: Personas
---

# Personas

There are two distinct "persona" mechanisms in the engine, and it helps to keep them apart:

1. **The agent's runtime persona** — the system-prompt string each `Agent` carries during the
   simulation. This is seeded inline by the engine from the entity, not from an LLM call.
2. **The descriptive persona** — a 2–3 sentence character sketch generated *after* the run by
   `simswarm/personas.py` to enrich the Data-tab profile cards.

This page covers both. Entity extraction (which produces the cast) is documented under
[Extractors](extractors.md) and in the [Agents & personas](../concepts/agents-and-personas.md)
concept page.

## Runtime persona (seeded inline)

In `Engine._create_agents`, every `Entity` becomes an `Agent` whose persona is built directly:

```python
persona=f"You are {entity.name}. {entity.summary}"
```

`simswarm/llm.py:build_context` then makes that persona the system message, prepends a belief
summary (`render_beliefs`, which maps numeric position/confidence to English bands like
"strongly opposed" / "firmly held"), adds the last few memory lines, and appends the
observation blocks as the user message. There is also an `agent_system.j2` template in
`simswarm/prompts/` (with `entity`, `goal`, `stance` slots), but the live engine path
constructs the system prompt from `agent.persona` directly rather than rendering that
template — treat the inline string as authoritative for the running engine.

## Descriptive persona generation

`simswarm/personas.py` produces richer profile text after all other extractors have run.

```python
async def extract_personas(
    profiles: list[dict],
    llm: LLMClient,
    *,
    goal: str = "",
) -> dict[str, str]:
```

`profiles` is the list of profile dicts from `extractor_activity.extract_profiles`, each with
at least `agent_id`, `name`, `posts`, `actions`, `rounds_active`, `platforms`, `sample_posts`,
and `sentiment_arc`. It returns a mapping `agent_id → persona_text`.

### Flow

1. **Short-circuit** — returns `{}` if `profiles` is empty.
2. **Prompt** — renders `extract_personas.j2` with the agents (keyed by `agent_id`) and the
   goal. The template asks for a concise 2–3 sentence persona per agent capturing stance,
   tone, and topical focus, with no meta-commentary, returned as a JSON object mapping
   `agent_id → persona_text`.
3. **Call** — one `llm.chat` at `temperature=0.4` (slightly warmer than relations, since
   these are descriptive). An empty response raises `PersonaExtractionError`.
4. **Parse** — `_parse_json_object` strips fences and slices between the first `{` and last
   `}` before `json.loads`. A non-object result raises.
5. **Filter and clamp** — entries whose key isn't a known `agent_id` are dropped
   (`personas.skip_unknown_agent`); non-string or empty values are dropped
   (`personas.skip_non_string` / `personas.skip_empty`); surviving strings are trimmed to
   `_MAX_PERSONA_CHARS = 1000`.

### Fallback contract

Any agent missing from the result — because the LLM omitted it, returned a non-string, or the
whole call failed — is expected to fall back to the one-line activity summary that
`extract_profiles` emits by default (`_profile_summary`, e.g. *"12 posts, 30 actions across 8
rounds on social."*). The caller merges the returned personas into the `profiles.json`
payload and keeps the one-liner for everyone else. This is why dropping is silent: the
fallback is always available.
