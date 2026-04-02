"""Extract rich simulation data from MiroShark SQLite databases.

All functions open DBs read-only and return JSON-serializable dicts/lists.
Used by worker_api.py after simulation completes, before pod termination.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

_POSITIVE = {"good", "great", "strong", "positive", "support", "gain", "rise", "up", "growth",
             "success", "win", "benefit", "improve", "surge", "rally", "boost", "confident",
             "optimistic", "bullish", "recovery", "progress", "opportunity"}
_NEGATIVE = {"bad", "poor", "weak", "negative", "loss", "fall", "down", "decline", "fail",
             "crash", "risk", "fear", "drop", "crisis", "concern", "threat", "bearish",
             "pessimistic", "collapse", "danger", "trouble", "panic"}


def _open_db(path: str) -> sqlite3.Connection | None:
    if not os.path.exists(path):
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _dict_rows(conn: sqlite3.Connection, query: str, params=()) -> list[dict]:
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def _sentiment_score(text: str) -> float:
    words = set(text.lower().split())
    pos = len(words & _POSITIVE)
    neg = len(words & _NEGATIVE)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 3)


def extract_posts(sim_dir: str) -> list[dict]:
    posts = []
    for platform, db_name in [("twitter", "twitter_simulation.db"), ("reddit", "reddit_simulation.db")]:
        db_path = os.path.join(sim_dir, db_name)
        conn = _open_db(db_path)
        if not conn:
            continue
        try:
            rows = _dict_rows(conn, """
                SELECT p.post_id, p.user_id, u.agent_id,
                       COALESCE(u.user_name, u.name, 'Agent ' || u.agent_id) AS agent_name,
                       p.content, p.created_at, p.num_likes, p.num_dislikes,
                       p.num_shares, p.num_reports, p.original_post_id
                FROM post p JOIN user u ON p.user_id = u.user_id
                ORDER BY p.created_at
            """)
            for r in rows:
                r["platform"] = platform
            posts.extend(rows)
        finally:
            conn.close()
    return posts


def extract_trades(sim_dir: str) -> list[dict]:
    db_path = os.path.join(sim_dir, "polymarket_simulation.db")
    conn = _open_db(db_path)
    if not conn:
        return []
    try:
        return _dict_rows(conn, """
            SELECT t.trade_id, t.user_id, COALESCE(u.user_name, u.name, 'Agent ' || u.agent_id) AS agent_name, u.agent_id,
                   t.market_id, t.side, t.outcome, t.shares, t.price, t.cost, t.created_at
            FROM trade t JOIN user u ON t.user_id = u.user_id
            ORDER BY t.created_at
        """)
    finally:
        conn.close()


def extract_market_curves(sim_dir: str) -> list[dict]:
    db_path = os.path.join(sim_dir, "polymarket_simulation.db")
    conn = _open_db(db_path)
    if not conn:
        return []
    try:
        markets = _dict_rows(conn, "SELECT market_id, question, outcome_a, outcome_b, reserve_a, reserve_b FROM market")
        trades = _dict_rows(conn, "SELECT market_id, side, outcome, shares, price, cost, created_at FROM trade ORDER BY created_at")
    finally:
        conn.close()

    curves = []
    for market in markets:
        mid = market["market_id"]
        ra, rb = float(market["reserve_a"]), float(market["reserve_b"])
        price_yes = rb / (ra + rb) if (ra + rb) > 0 else 0.5
        points = [{"trade_idx": 0, "price_yes": round(price_yes, 4), "price_no": round(1 - price_yes, 4), "volume": 0}]

        market_trades = [t for t in trades if t["market_id"] == mid]
        cumulative_volume = 0.0
        for i, t in enumerate(market_trades):
            cumulative_volume += abs(float(t.get("cost", 0)))
            if t["side"] == "buy":
                if t["outcome"] == market["outcome_a"]:
                    ra -= float(t["shares"])
                    rb += float(t["cost"])
                else:
                    rb -= float(t["shares"])
                    ra += float(t["cost"])
            else:
                if t["outcome"] == market["outcome_a"]:
                    ra += float(t["shares"])
                    rb -= float(t["cost"])
                else:
                    rb += float(t["shares"])
                    ra -= float(t["cost"])
            price_yes = rb / (ra + rb) if (ra + rb) > 0 else 0.5
            points.append({
                "trade_idx": i + 1,
                "price_yes": round(price_yes, 4),
                "price_no": round(1 - price_yes, 4),
                "volume": round(cumulative_volume, 2),
            })

        curves.append({
            "market_id": mid,
            "question": market["question"],
            "outcome_a": market["outcome_a"],
            "outcome_b": market["outcome_b"],
            "points": points,
        })
    return curves


def extract_agent_trajectories(sim_dir: str, actions: list[dict], round_window: int = 20) -> list[dict]:
    agents = {}
    for platform, db_name in [("twitter", "twitter_simulation.db"), ("reddit", "reddit_simulation.db")]:
        db_path = os.path.join(sim_dir, db_name)
        conn = _open_db(db_path)
        if not conn:
            continue
        try:
            for row in _dict_rows(conn, "SELECT agent_id, user_name, name FROM user"):
                aid = row["agent_id"]
                if aid not in agents:
                    agents[aid] = {"agent_id": aid, "name": row["user_name"] or row["name"] or f"Agent {aid}", "rounds": []}
        finally:
            conn.close()

    if not agents or not actions:
        return list(agents.values())

    max_round = max((a.get("round_num", a.get("round", 0)) or 0 for a in actions), default=0)

    for aid, agent in agents.items():
        for win_start in range(0, max_round + 1, round_window):
            win_end = win_start + round_window
            window_actions = [a for a in actions
                             if a.get("agent_id") == aid
                             and win_start <= (a.get("round_num", a.get("round", 0)) or 0) < win_end]
            posts = [a for a in window_actions if a.get("action_type") == "CREATE_POST"]
            post_texts = " ".join(
                a.get("action_args", {}).get("content", "") for a in posts if isinstance(a.get("action_args"), dict)
            )
            agent["rounds"].append({
                "round": win_start,
                "posts": len(posts),
                "actions": len(window_actions),
                "sentiment": _sentiment_score(post_texts) if post_texts.strip() else 0.0,
            })

    return list(agents.values())


def extract_engagement_summary(actions: list[dict], round_window: int = 10) -> list[dict]:
    if not actions:
        return []
    max_round = max((a.get("round_num", a.get("round", 0)) or 0 for a in actions), default=0)
    summary = []
    for win_start in range(0, max_round + 1, round_window):
        win_end = win_start + round_window
        window = [a for a in actions if win_start <= (a.get("round_num", a.get("round", 0)) or 0) < win_end]
        posts = sum(1 for a in window if a.get("action_type") == "CREATE_POST")
        likes = sum(1 for a in window if a.get("action_type") in ("LIKE_POST", "LIKE_COMMENT"))
        comments = sum(1 for a in window if a.get("action_type") == "CREATE_COMMENT")
        active = len(set(a.get("agent_id") for a in window))
        summary.append({
            "round": win_start,
            "total_posts": posts,
            "total_likes": likes,
            "total_comments": comments,
            "active_agents": active,
        })
    return summary


def extract_top_posts(sim_dir: str, limit: int = 50) -> list[dict]:
    posts = []
    for platform, db_name in [("twitter", "twitter_simulation.db"), ("reddit", "reddit_simulation.db")]:
        db_path = os.path.join(sim_dir, db_name)
        conn = _open_db(db_path)
        if not conn:
            continue
        try:
            rows = _dict_rows(conn, f"""
                SELECT p.post_id, u.agent_id,
                       COALESCE(u.user_name, u.name, 'Agent ' || u.agent_id) AS agent_name,
                       p.content, p.created_at,
                       p.num_likes, p.num_dislikes, p.num_shares,
                       (p.num_likes + p.num_shares) AS engagement
                FROM post p JOIN user u ON p.user_id = u.user_id
                WHERE p.content != ''
                ORDER BY engagement DESC
                LIMIT {limit}
            """)
            for r in rows:
                r["platform"] = platform
            posts.extend(rows)
        finally:
            conn.close()
    posts.sort(key=lambda p: p.get("engagement", 0), reverse=True)
    return posts[:limit]


def extract_social_graph(sim_dir: str) -> dict:
    edges = []
    for platform, db_name in [("twitter", "twitter_simulation.db"), ("reddit", "reddit_simulation.db")]:
        db_path = os.path.join(sim_dir, db_name)
        conn = _open_db(db_path)
        if not conn:
            continue
        try:
            rows = _dict_rows(conn, """
                SELECT f.follower_id, u1.user_name AS follower_name,
                       f.followee_id, u2.user_name AS followee_name,
                       f.created_at
                FROM follow f
                JOIN user u1 ON f.follower_id = u1.user_id
                JOIN user u2 ON f.followee_id = u2.user_id
            """)
            for r in rows:
                r["platform"] = platform
            edges.extend(rows)
        finally:
            conn.close()

    pairs = set()
    for e in edges:
        pairs.add((e["follower_id"], e["followee_id"]))
    mutual = []
    seen = set()
    for a, b in pairs:
        if (b, a) in pairs and (min(a, b), max(a, b)) not in seen:
            seen.add((min(a, b), max(a, b)))
            mutual.append({"agent_a": a, "agent_b": b})

    return {"edges": edges, "mutual_follows": mutual}


def extract_profiles(sim_dir: str) -> list[dict]:
    profiles = []
    reddit_path = os.path.join(sim_dir, "reddit_profiles.json")
    if os.path.exists(reddit_path):
        with open(reddit_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                profiles = data

    twitter_path = os.path.join(sim_dir, "twitter_profiles.csv")
    if os.path.exists(twitter_path):
        import csv
        with open(twitter_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                agent_name = row.get("user_name", row.get("name", ""))
                matched = False
                for p in profiles:
                    if p.get("user_name") == agent_name or p.get("name") == agent_name:
                        p["twitter_profile"] = row
                        matched = True
                        break
                if not matched:
                    profiles.append({"name": agent_name, "twitter_profile": row})

    return profiles


def extract_all(sim_dir: str, actions: list[dict]) -> dict[str, object]:
    return {
        "market_curves.json": extract_market_curves(sim_dir),
        "agent_trajectories.json": extract_agent_trajectories(sim_dir, actions),
        "engagement_summary.json": extract_engagement_summary(actions),
        "top_posts.json": extract_top_posts(sim_dir),
        "posts.json": extract_posts(sim_dir),
        "trades.json": extract_trades(sim_dir),
        "social_graph.json": extract_social_graph(sim_dir),
        "profiles.json": extract_profiles(sim_dir),
    }
