# Thread Action Execution Results Into Chat Log — Fix `$NaN` Trades

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the data environments compute at execution time (cost, executed price, filled shares, proceeds) into the chat log so `extract_market_data` can emit the schema `TradeFeed.vue` needs, eliminating `$NaN` / `NaN%` in the Trades panel.

**Architecture:**
Extend `ActionRecord` with an optional `action_result: dict | None` field. Populate it in the engine loop from `ActionResult.data`. Normalize the market env's `ActionResult.data` to a consistent shape (`outcome`, `price`, `cost`, `shares`, `proceeds`). Rewrite `extract_market_data` to read from `action_result` and emit `{trade_id, side, agent_name, outcome, price, cost}` — the schema `TradeFeed.vue` already renders.

**Tech Stack:** Python 3.11+, dataclasses, pytest-asyncio.

**Non-goals:** Frontend changes are not in scope — the Vue component already has the right template, it just needs the right fields. No new API surface; no MinIO schema version bump (additive JSON fields are backwards-compatible with older report fixtures).

---

## File Structure

**Modify:**
- `simswarm/types.py` — add `action_result: dict | None = None` to `ActionRecord`.
- `simswarm/engine.py` — populate `action_result` from the env's `ActionResult.data` at record-build time.
- `simswarm/environments/market.py` — have `_handle_buy` / `_handle_sell` return a consistent `ActionResult.data` containing `{outcome, price, cost, shares, proceeds}`.
- `simswarm/adapter.py` — include `action_result` in `adapt_chat_log` output.
- `simswarm/extractor_market_social.py` — rewrite `extract_market_data` to read from `action_result` and emit the frontend schema.
- `tests/engine/extractor_fixtures.py` — move `price` out of `action_args` into `action_result`, add `cost` / `outcome`, so fixtures reflect what production records actually look like.
- `tests/engine/test_extractor_graph_market.py` — update assertions to the new output schema.

**New tests:**
- `tests/engine/test_types_action_record.py` — contract test for the new field.
- Added test methods inside the existing `tests/engine/test_market_env.py` and `tests/engine/test_engine.py`.

---

## Task 1: Add `action_result` field to `ActionRecord`

**Files:**
- Modify: `simswarm/types.py:152-162`
- Create: `tests/engine/test_types_action_record.py`

- [ ] **Step 1: Write the failing test**

Create `tests/engine/test_types_action_record.py`:

```python
"""Contract tests for ActionRecord."""
from __future__ import annotations

from simswarm.types import ActionRecord


class TestActionRecordActionResult:
    def test_action_result_defaults_to_none(self):
        record = ActionRecord(
            round_num=1, agent_id="a", agent_name="A",
            action_type="do_nothing", platform="social",
            action_args={},
        )
        assert record.action_result is None

    def test_action_result_accepts_dict(self):
        record = ActionRecord(
            round_num=1, agent_id="a", agent_name="A",
            action_type="buy_shares", platform="market",
            action_args={"market_id": "m1", "amount": 100},
            action_result={"cost": 100.0, "price": 0.62, "shares": 161.3},
        )
        assert record.action_result == {"cost": 100.0, "price": 0.62, "shares": 161.3}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/engine/test_types_action_record.py -v`
Expected: FAIL — `TypeError: ActionRecord.__init__() got an unexpected keyword argument 'action_result'`.

- [ ] **Step 3: Add the field**

In `simswarm/types.py`, update the `ActionRecord` dataclass:

```python
@dataclass
class ActionRecord:
    """A logged agent action for the chat log."""
    round_num: int
    agent_id: str
    agent_name: str
    action_type: str
    platform: str
    action_args: dict[str, Any]
    timestamp: str | None = None
    success: bool = True
    action_result: dict[str, Any] | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/engine/test_types_action_record.py -v`
Expected: 2 passed.

- [ ] **Step 5: Run full type-adjacent test suite to catch positional-arg callers**

Run: `pytest tests/engine/ -x -q`
Expected: PASS (the field is at the end with a default, so no existing call is broken).

- [ ] **Step 6: Commit**

```bash
git add simswarm/types.py tests/engine/test_types_action_record.py
git commit -m "feat(types): add optional action_result to ActionRecord"
```

---

## Task 2: Populate `action_result` in the engine loop

**Files:**
- Modify: `simswarm/engine.py:95-112`
- Modify: `tests/engine/test_engine.py` (add one test method)

- [ ] **Step 1: Write the failing test**

Add to `tests/engine/test_engine.py`. First check the file's existing imports and test style — copy that convention. Then add this test class:

```python
class TestActionResultPropagation:
    """engine.step must copy ActionResult.data onto ActionRecord.action_result."""

    @pytest.mark.asyncio
    async def test_buy_shares_result_data_reaches_chat_log(self):
        # Minimal engine run with a market env and a stub LLM that emits one
        # buy_shares tool call. Assert the resulting ActionRecord carries
        # action_result with the env's data dict.
        from simswarm.engine import Engine
        from simswarm.environments.market import MarketEnvironment, MarketConfig
        from simswarm.types import (
            Agent, AgentActivityConfig, BeliefState, EngineConfig,
            Entity, EnvironmentConfig, SimulationConfig,
        )

        class StubLLM:
            """Emits one buy_shares call, then nothing."""
            def __init__(self):
                self.calls = 0

            async def chat(self, messages, tools=None):
                from simswarm.types import LLMResponse
                self.calls += 1
                if self.calls == 1:
                    return LLMResponse(
                        content="",
                        tool_calls=[{
                            "name": "buy_shares",
                            "args": {"market_id": "m0", "outcome": "yes", "amount": 50.0},
                        }],
                    )
                return LLMResponse(content="", tool_calls=[])

            async def close(self): pass

        fast = StubLLM()
        smart = StubLLM()
        config = SimulationConfig(
            seed_text="",
            goal="",
            entities=[Entity(id="t1", name="Trader", stance="neutral", influence_weight=1.0)],
            environments=[EnvironmentConfig(
                type="market",
                params={"markets": [{"question": "Will X?", "initial_price_yes": 0.5}]},
            )],
            rounds=1,
            concurrency=1,
        )
        engine = Engine(fast_llm=fast, smart_llm=smart, engine_config=EngineConfig(concurrency=1))
        result = await engine.run(config)

        trade_records = [r for r in result.chat_log if r.action_type == "buy_shares"]
        assert trade_records, "expected at least one buy_shares record"
        rec = trade_records[0]
        assert rec.action_result is not None
        assert rec.action_result.get("cost") == pytest.approx(50.0)
        assert "price" in rec.action_result
        assert "shares" in rec.action_result
```

Note: if `LLMResponse` lives in a different module, adjust the import to match. Check `simswarm/llm.py` or wherever `response.tool_calls` is constructed.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/engine/test_engine.py::TestActionResultPropagation -v`
Expected: FAIL — `rec.action_result is None` because the engine drops `result.data`.

- [ ] **Step 3: Implement the fix**

In `simswarm/engine.py`, change the `ActionRecord(...)` construction inside `step_agent` (lines 107-112). Before:

```python
records.append(ActionRecord(
    round_num=round_num, agent_id=agent.id,
    agent_name=agent.name, action_type=action_name,
    platform=target_env, action_args=action_args,
    success=result.success if result else False,
))
```

After:

```python
records.append(ActionRecord(
    round_num=round_num, agent_id=agent.id,
    agent_name=agent.name, action_type=action_name,
    platform=target_env, action_args=action_args,
    success=result.success if result else False,
    action_result=dict(result.data) if result and result.data else None,
))
```

Use `dict(result.data)` (shallow copy) so downstream mutations to the env's internal state don't retroactively change the logged record.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/engine/test_engine.py::TestActionResultPropagation -v`
Expected: PASS. (`cost == 50.0` comes from the market env; price and shares from Task 3 — if Task 3 hasn't landed yet, this test may still fail on the `price` / `shares` assertions. That's expected — leave the assertions; they pin the Task 3 contract. Alternative: split this test so one part asserts `cost` only and runs at Task 2, the rest runs at Task 3.)

If you prefer the split:
- At Task 2: assert only `rec.action_result.get("cost") == pytest.approx(50.0)`.
- At Task 3: add the `price` and `shares` assertions.

Pick the split for cleaner commit history. Update the test to match whichever task you're on.

- [ ] **Step 5: Commit**

```bash
git add simswarm/engine.py tests/engine/test_engine.py
git commit -m "feat(engine): propagate ActionResult.data onto ActionRecord"
```

---

## Task 3: Normalize the market env's `ActionResult.data`

**Files:**
- Modify: `simswarm/environments/market.py:192-241` (`_handle_buy` and `_handle_sell`)
- Modify: `tests/engine/test_market_env.py` (add test methods)

- [ ] **Step 1: Write the failing tests**

Add these methods at the bottom of `tests/engine/test_market_env.py`:

```python
class TestActionResultShape:
    """Buy and sell must return a consistent ActionResult.data schema."""

    def _env(self):
        env = MarketEnvironment(MarketConfig(
            markets=[{"question": "Will X?", "initial_price_yes": 0.5}],
            initial_balance=1000.0,
        ))
        trader = _make_agent("t1")
        env.register_agent(trader)
        return env, trader, list(env.markets.keys())[0]

    def test_buy_data_includes_outcome_price_cost_shares(self):
        env, trader, mid = self._env()
        result = env.execute_action(trader, Action(
            agent_id="t1", environment="market",
            action_type="buy_shares",
            args={"market_id": mid, "outcome": "yes", "amount": 50.0},
        ))
        assert result.success
        data = result.data
        assert data["outcome"] == "yes"
        assert data["cost"] == pytest.approx(50.0)
        assert data["shares"] > 0
        assert 0 < data["price"] < 1  # executed price_yes after fill
        assert data.get("market_id") == mid

    def test_sell_data_includes_outcome_price_proceeds_shares(self):
        env, trader, mid = self._env()
        env.execute_action(trader, Action(
            agent_id="t1", environment="market",
            action_type="buy_shares",
            args={"market_id": mid, "outcome": "yes", "amount": 50.0},
        ))
        held = env.portfolios["t1"].shares[mid]["yes"]
        result = env.execute_action(trader, Action(
            agent_id="t1", environment="market",
            action_type="sell_shares",
            args={"market_id": mid, "outcome": "yes", "shares": held / 2},
        ))
        assert result.success
        data = result.data
        assert data["outcome"] == "yes"
        assert data["proceeds"] > 0
        assert data["shares"] == pytest.approx(held / 2)
        assert 0 < data["price"] < 1
        assert data.get("market_id") == mid
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_market_env.py::TestActionResultShape -v`
Expected: FAIL — current `_handle_buy` returns `{shares, cost}` (missing outcome/price/market_id); `_handle_sell` returns `{usd}` only.

- [ ] **Step 3: Update `_handle_buy` in `simswarm/environments/market.py`**

Replace the body from line 194 through line 217:

```python
def _handle_buy(self, agent: Agent, args: dict) -> ActionResult:
    market_id = args.get("market_id", "")
    outcome = args.get("outcome", "yes")
    amount = args.get("amount", 0.0)
    if market_id not in self.markets:
        return ActionResult(success=False, data={"error": "Market not found"})
    portfolio = self.portfolios[agent.id]
    if portfolio.balance < amount:
        return ActionResult(success=False, data={"error": "Insufficient balance"})
    market = self.markets[market_id]
    if outcome == "yes":
        shares = market.buy_yes(amount)
        executed_price = market.price_yes
    else:
        shares = market.buy_no(amount)
        executed_price = market.price_no
    portfolio.balance -= amount
    if market_id not in portfolio.shares:
        portfolio.shares[market_id] = {"yes": 0.0, "no": 0.0}
    portfolio.shares[market_id][outcome] += shares
    trade_record = {
        "market_id": market_id, "outcome": outcome,
        "shares": shares, "cost": amount, "price": executed_price,
        "round": self.current_round,
    }
    self._trades.append({"agent_id": agent.id, "side": "buy", **trade_record})
    return ActionResult(success=True, data={"side": "buy", **trade_record})
```

- [ ] **Step 4: Update `_handle_sell`**

Replace the body from line 219 through line 241:

```python
def _handle_sell(self, agent: Agent, args: dict) -> ActionResult:
    market_id = args.get("market_id", "")
    outcome = args.get("outcome", "yes")
    shares = args.get("shares", 0.0)
    if market_id not in self.markets:
        return ActionResult(success=False, data={"error": "Market not found"})
    portfolio = self.portfolios[agent.id]
    held = portfolio.shares.get(market_id, {}).get(outcome, 0.0)
    if held < shares:
        return ActionResult(success=False, data={"error": "Insufficient shares"})
    market = self.markets[market_id]
    if outcome == "yes":
        proceeds = market.sell_yes(shares)
        executed_price = market.price_yes
    else:
        proceeds = market.sell_no(shares)
        executed_price = market.price_no
    portfolio.shares[market_id][outcome] -= shares
    portfolio.balance += proceeds
    trade_record = {
        "market_id": market_id, "outcome": outcome,
        "shares": shares, "proceeds": proceeds, "price": executed_price,
        "round": self.current_round,
    }
    self._trades.append({"agent_id": agent.id, "side": "sell", **trade_record})
    return ActionResult(success=True, data={"side": "sell", **trade_record})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/engine/test_market_env.py -v`
Expected: PASS. (Run the full market env file — the existing `TestPortfolio` tests still pass because `portfolio.balance` and `portfolio.shares` logic is unchanged.)

- [ ] **Step 6: Re-run the Task 2 engine test — it should now pass fully**

If you split the Task 2 assertions, extend them now:

```python
assert rec.action_result.get("cost") == pytest.approx(50.0)
assert 0 < rec.action_result.get("price") < 1
assert rec.action_result.get("shares") > 0
assert rec.action_result.get("side") == "buy"
```

Run: `pytest tests/engine/test_engine.py::TestActionResultPropagation -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add simswarm/environments/market.py tests/engine/test_market_env.py tests/engine/test_engine.py
git commit -m "feat(market): unify buy/sell ActionResult shape with outcome/price/cost/shares"
```

---

## Task 4: Include `action_result` in `adapt_chat_log` output

**Files:**
- Modify: `simswarm/adapter.py:24-43`
- Modify: `tests/engine/test_adapter.py` (add one test)

- [ ] **Step 1: Write the failing test**

Read `tests/engine/test_adapter.py` to understand existing test structure. Then add:

```python
class TestAdaptChatLogActionResult:
    def test_action_result_preserved_when_present(self):
        from simswarm.types import ActionRecord
        from simswarm.adapter import adapt_chat_log
        record = ActionRecord(
            round_num=1, agent_id="a", agent_name="A",
            action_type="buy_shares", platform="market",
            action_args={"market_id": "m0", "amount": 100},
            action_result={"side": "buy", "cost": 100.0, "price": 0.52, "shares": 192.3},
        )
        out = adapt_chat_log([record])
        assert out[0]["action_result"] == {
            "side": "buy", "cost": 100.0, "price": 0.52, "shares": 192.3,
        }

    def test_action_result_omitted_is_none_in_output(self):
        from simswarm.types import ActionRecord
        from simswarm.adapter import adapt_chat_log
        record = ActionRecord(
            round_num=1, agent_id="a", agent_name="A",
            action_type="create_post", platform="social",
            action_args={"text": "hi"},
        )
        out = adapt_chat_log([record])
        assert out[0]["action_result"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/engine/test_adapter.py::TestAdaptChatLogActionResult -v`
Expected: FAIL — `KeyError: 'action_result'` in the output dict.

- [ ] **Step 3: Update `adapt_chat_log`**

In `simswarm/adapter.py`, extend the dict emitted per record:

```python
def adapt_chat_log(chat_log: list[ActionRecord]) -> list[dict]:
    """Convert ActionRecords to dicts consumed by the SaaS frontend."""
    result = []
    for record in chat_log:
        result.append({
            "round_num": record.round_num,
            "agent_id": record.agent_id,
            "agent_name": record.agent_name,
            "action_type": record.action_type,
            "platform": record.platform,
            "action_args": record.action_args,
            "action_result": record.action_result,
            "timestamp": record.timestamp,
            "success": record.success,
        })
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/engine/test_adapter.py -v`
Expected: PASS (new tests pass; existing adapter tests still pass — additive field).

- [ ] **Step 5: Commit**

```bash
git add simswarm/adapter.py tests/engine/test_adapter.py
git commit -m "feat(adapter): include action_result in chat_log output"
```

---

## Task 5: Rewrite `extract_market_data` for the frontend schema

**Files:**
- Modify: `simswarm/extractor_market_social.py:51-76`
- Modify: `tests/engine/extractor_fixtures.py` (move price into action_result; add cost/outcome)
- Modify: `tests/engine/test_extractor_graph_market.py:61-96` (update assertions to the new schema)

- [ ] **Step 1: Update the fixture to reflect real engine output**

In `tests/engine/extractor_fixtures.py`, replace the two trade records (buy at lines 94-104 and sell at lines 105-115) with:

```python
    # Round 2 — agent-beta buys on market
    ActionRecord(
        round_num=2,
        agent_id="agent-beta",
        agent_name="Bob",
        action_type="buy_shares",
        platform="polymarket",
        action_args={"market_id": "gdp_rise_q4", "outcome": "yes", "amount": 250},
        action_result={"side": "buy", "market_id": "gdp_rise_q4", "outcome": "yes",
                       "cost": 250.0, "shares": 403.2, "price": 0.62, "round": 2},
        timestamp="2026-04-08T10:13:00Z",
        success=True,
    ),
    # Round 3 — agent-alpha sells shares
    ActionRecord(
        round_num=3,
        agent_id="agent-alpha",
        agent_name="Alice",
        action_type="sell_shares",
        platform="polymarket",
        action_args={"market_id": "inflation_below_3pct", "outcome": "no", "shares": 100},
        action_result={"side": "sell", "market_id": "inflation_below_3pct", "outcome": "no",
                       "proceeds": 45.0, "shares": 100.0, "price": 0.45, "round": 3},
        timestamp="2026-04-08T10:20:00Z",
        success=True,
    ),
```

Note the changes:
- `market` → `market_id` (matches engine)
- Added `outcome` arg
- Sell now uses `shares`, not `amount`
- `price` moved from `action_args` (where production never puts it) into `action_result`

- [ ] **Step 2: Write the new-schema extractor tests**

Replace `class TestExtractMarketData` in `tests/engine/test_extractor_graph_market.py` with:

```python
class TestExtractMarketData:
    def test_returns_list_of_dicts(self):
        result = extract_market_data(SAMPLE_LOG)
        assert isinstance(result, list)
        assert all(isinstance(t, dict) for t in result)

    def test_only_trade_actions_returned(self):
        for trade in extract_market_data(SAMPLE_LOG):
            assert trade["side"] in ("buy", "sell")

    def test_correct_trade_count(self):
        assert len(extract_market_data(SAMPLE_LOG)) == 2

    def test_frontend_schema_fields_present(self):
        # TradeFeed.vue reads: trade_id, side, agent_name, outcome, price, cost
        for trade in extract_market_data(SAMPLE_LOG):
            for field in ("trade_id", "side", "agent_name", "outcome", "price", "cost"):
                assert field in trade, f"missing {field} in {trade}"

    def test_side_derived_from_action_type(self):
        sides = {t["side"] for t in extract_market_data(SAMPLE_LOG)}
        assert sides == {"buy", "sell"}

    def test_buy_cost_from_action_result(self):
        buys = [t for t in extract_market_data(SAMPLE_LOG) if t["side"] == "buy"]
        assert buys[0]["cost"] == pytest.approx(250.0)
        assert buys[0]["price"] == pytest.approx(0.62)
        assert buys[0]["outcome"] == "yes"

    def test_sell_cost_is_proceeds(self):
        # For sells we expose proceeds via the `cost` key so the frontend
        # doesn't need to branch. A sell's "cost" is negative from the agent's
        # cash-flow perspective? No — keep it as the dollar magnitude (proceeds)
        # so the UI column `$NN` is always non-negative.
        sells = [t for t in extract_market_data(SAMPLE_LOG) if t["side"] == "sell"]
        assert sells[0]["cost"] == pytest.approx(45.0)
        assert sells[0]["price"] == pytest.approx(0.45)
        assert sells[0]["outcome"] == "no"

    def test_trade_id_is_stable_and_unique(self):
        trades = extract_market_data(SAMPLE_LOG)
        ids = [t["trade_id"] for t in trades]
        assert len(ids) == len(set(ids))

    def test_empty_log_returns_empty_list(self):
        assert extract_market_data([]) == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/engine/test_extractor_graph_market.py::TestExtractMarketData -v`
Expected: FAIL — current extractor emits `{agent_id, agent_name, round_num, action_type, platform, market, amount, timestamp, success}` only.

- [ ] **Step 4: Rewrite `extract_market_data`**

Replace `simswarm/extractor_market_social.py:51-76` with:

```python
def extract_market_data(chat_log: list[ActionRecord]) -> list[dict]:
    """Extract trade records from buy_shares / sell_shares actions.

    Emits the schema consumed by frontend/src/components/data/TradeFeed.vue:
      - trade_id: stable synthetic id (agent_id + round + index)
      - side: "buy" | "sell" (derived from action_type)
      - agent_id, agent_name, round_num, platform
      - market_id, outcome
      - price: executed price at fill time
      - cost: USD spent (buys) or proceeds received (sells) — dollar magnitude
      - shares: shares bought or sold
      - amount_requested: original USD the agent asked to spend (buys only)
      - timestamp, success

    Reads executed values from record.action_result (populated by the engine
    from the env's ActionResult.data). Falls back to action_args for backward
    compatibility with pre-Task-3 chat logs.
    """
    result: list[dict] = []
    for idx, record in enumerate(chat_log):
        if not is_trade(record.action_type):
            continue
        args = record.action_args or {}
        res = record.action_result or {}
        side = "buy" if record.action_type.lower() == "buy_shares" else "sell"

        if side == "buy":
            cost = res.get("cost", args.get("amount"))
            shares = res.get("shares")
        else:
            # Sell: `cost` column in the UI shows proceeds magnitude.
            cost = res.get("proceeds")
            shares = res.get("shares", args.get("shares"))

        entry: dict[str, Any] = {
            "trade_id": f"{record.agent_id}-r{record.round_num}-{idx}",
            "side": side,
            "agent_id": record.agent_id,
            "agent_name": record.agent_name,
            "round_num": record.round_num,
            "platform": record.platform,
            "market_id": res.get("market_id", args.get("market_id", args.get("market", ""))),
            "outcome": res.get("outcome", args.get("outcome", "")),
            "price": res.get("price"),
            "cost": cost,
            "shares": shares,
            "amount_requested": args.get("amount"),
            "timestamp": record.timestamp,
            "success": record.success,
        }
        result.append(entry)
    return result
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/engine/test_extractor_graph_market.py -v`
Expected: PASS (all of `TestExtractMarketData` + the `TestExtractSocialGraph` class — the latter is unaffected).

- [ ] **Step 6: Run the broader engine suite to catch callers that relied on old keys**

Run: `pytest tests/engine/ -x -q`
Expected: PASS. If anything references the old `market` key (without `_id`) or the old `amount` key on a trade entry, update it — search for `"market":` in `simswarm/` and `saas/jobs/`:

```bash
grep -rn '\["market"\]\|t\["amount"\]' simswarm/ saas/jobs/ tests/
```

For any legitimate hit, either:
- Add a transitional alias (`entry["market"] = entry["market_id"]`), **or**
- Update the caller to the new name.

Prefer updating callers. Aliases rot.

- [ ] **Step 7: Commit**

```bash
git add simswarm/extractor_market_social.py tests/engine/extractor_fixtures.py tests/engine/test_extractor_graph_market.py
git commit -m "feat(extractor): emit frontend trade schema from action_result"
```

---

## Task 6: Verify end-to-end with the existing run_job_v2 test

**Files:**
- Modify (if needed): `tests/engine/test_run_job_v2.py::test_trades_json_contains_buy_shares`
- Run: the full suite

- [ ] **Step 1: Read the current test**

Run: `grep -n "test_trades_json_contains_buy_shares" tests/engine/test_run_job_v2.py`
Then read the surrounding 40 lines to see what it asserts about `trades.json`.

- [ ] **Step 2: Update assertions if they reference the old schema**

If the test asserts keys like `market` or `amount` on a trade entry, replace with `market_id` and `cost` respectively. Add assertions for the new fields:

```python
assert "trade_id" in data[0]
assert data[0]["side"] == "buy"
assert data[0]["cost"] is not None
assert data[0]["price"] is not None
```

If the test already uses broad assertions (`assert len(data) > 0`) leave it alone — no change required.

- [ ] **Step 3: Run the full backend suite**

Run: `pytest -x -q`
Expected: PASS.

- [ ] **Step 4: Run the frontend vitest suite**

Run: `cd frontend && npm test -- --run`
Expected: PASS. `TradeFeed.vue` tests use hand-built fixtures with `{trade_id, agent_name, side, outcome, price, cost}` already (see `data.spec.js:204-205`), so no frontend changes are required. If any test constructs a trade via the *old* backend shape, update it.

- [ ] **Step 5: Commit if any test edits were needed**

```bash
git add tests/engine/test_run_job_v2.py frontend/...
git commit -m "test: assert new trade schema in end-to-end tests"
```

(Skip the commit if nothing changed.)

---

## Task 7: Smoke-test on a real sim

**Files:** none — operational.

- [ ] **Step 1: Run a small sim through the full pipeline**

The fastest path is the in-repo smoke path — a local sim that hits the runner without a GPU. If that doesn't exist, queue a real small-tier sim through the SaaS UI with a seed document that'll produce market activity.

- [ ] **Step 2: Pull the resulting `trades.json` from MinIO**

```bash
mc cat <alias>/<bucket>/<job_id>/trades.json | jq '.[0]'
```

Expected: entry contains non-null `price`, non-null `cost`, and a `side` string. No NaN.

- [ ] **Step 3: Open the Data dashboard for the job in the frontend**

Navigate to the job's detail page, open the data tab, confirm the Trades panel renders real dollar amounts and percentages (no `$NaN`, no `NaN%`) and shows a mix of BUY and SELL labels (not the all-SELL screenshot that prompted this plan).

- [ ] **Step 4: If everything looks good, no further commit is needed.**

If you hit any surprise, write down the reproduction steps in a new spec before patching — resist one-off fixes at this stage.

---

## Self-Review Checklist (for the author)

- [x] **Spec coverage:** every piece of the root cause ("engine drops ActionResult.data", "buy and sell have inconsistent data dicts", "extractor emits wrong schema", "chat_log adapter doesn't forward the new field") has a task.
- [x] **Placeholder scan:** no TBD / "implement later" / "handle edge cases" strings. Each step shows code.
- [x] **Type consistency:** `action_result` (dict | None) is used uniformly; `market_id` replaces `market` everywhere; `cost` means "dollar magnitude" in both buy and sell rows; `side` is always `"buy"` or `"sell"`.
- [x] **No dead branches:** the extractor still falls back to `action_args` for pre-Task-3 chat logs so replaying an old MinIO artifact in the report pipeline doesn't crash. New runs populate `action_result`.

## Rollout notes

- **Backwards compatibility for old MinIO artifacts:** the new `extract_market_data` reads `action_result` first, then falls back to `action_args`. Old trade records still produce entries — they'll just have `price: None, cost: None, shares: None`. That matches the current broken state; no regression.
- **JSON size:** `action_result` adds ~100 bytes per trade record to `chat_log.json`. Negligible.
- **No DB migrations.** No API contract bump. No frontend code change.
