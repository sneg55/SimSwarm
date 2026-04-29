"""Unified social environment — replaces separate Twitter/Reddit platforms.

Configurable threading, voting mode, feed algorithm, and virality.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field

from simswarm.types import Action, ActionResult, Agent, Event, Observation, Tool


@dataclass
class SocialConfig:
    threading: bool = True
    voting_mode: str = "likes_only"
    recency_weight: float = 0.3
    popularity_weight: float = 0.4
    relevance_weight: float = 0.3
    echo_chamber_strength: float = 0.5
    viral_threshold: int = 5


@dataclass
class Post:
    id: str
    author_id: str
    author_name: str
    text: str
    parent_id: str | None = None
    likes: int = 0
    dislikes: int = 0
    reposts: int = 0
    created_round: int = 0
    voters: set[str] = field(default_factory=set)


class SocialEnvironment:
    """Unified social platform with configurable features."""

    name = "social"

    def __init__(self, config: SocialConfig, current_round: int = 0):
        self.config = config
        self.current_round = current_round
        self.posts: dict[str, Post] = {}
        self.follows: dict[str, set[str]] = {}
        self._pending_events: list[Event] = []
        self._new_viral: set[str] = set()

    def execute_action(self, agent: Agent, action: Action) -> ActionResult:
        handler = {
            "create_post": self._handle_create_post,
            "reply": self._handle_reply,
            "vote": self._handle_vote,
            "repost": self._handle_repost,
            "follow": self._handle_follow,
            "do_nothing": self._handle_noop,
        }.get(action.action_type)
        if handler is None:
            return ActionResult(success=False, data={"error": f"Unknown action: {action.action_type}"})
        return handler(agent, action.args)

    def get_observations(self, agent: Agent) -> Observation:
        ranked = self._rank_feed(agent.id)
        lines = []
        for post in ranked[:20]:
            score = post.likes - post.dislikes
            lines.append(
                f"post_id={post.id} [{post.author_name}] {post.text} (score: {score})"
            )
            if self.config.threading:
                replies = [p for p in self.posts.values() if p.parent_id == post.id]
                for reply in replies[:3]:
                    lines.append(
                        f"  -> post_id={reply.id} [{reply.author_name}] {reply.text}"
                    )
        content = "\n".join(lines) if lines else "(no posts yet)"
        return Observation(environment=self.name, content=content)

    def get_tools(self) -> list[Tool]:
        tools = [
            Tool(name="create_post", description="Create a new post",
                 parameters={"type": "object", "properties": {
                     "text": {"type": "string", "description": "Post content"},
                 }, "required": ["text"]}),
            Tool(name="reply", description="Reply to an existing post. Use the post_id shown in the feed.",
                 parameters={"type": "object", "properties": {
                     "post_id": {"type": "string", "description": "The post_id from the feed (UUID)"},
                     "text": {"type": "string"},
                 }, "required": ["post_id", "text"]}),
            Tool(name="vote", description="Vote on a post (value: 1 for like, -1 for dislike). Use the post_id shown in the feed.",
                 parameters={"type": "object", "properties": {
                     "post_id": {"type": "string", "description": "The post_id from the feed (UUID)"},
                     "value": {"type": "integer", "enum": [1, -1]},
                 }, "required": ["post_id", "value"]}),
            Tool(name="repost", description="Repost someone's post. Use the post_id shown in the feed.",
                 parameters={"type": "object", "properties": {
                     "post_id": {"type": "string", "description": "The post_id from the feed (UUID)"},
                 }, "required": ["post_id"]}),
            Tool(name="follow", description="Follow another agent",
                 parameters={"type": "object", "properties": {
                     "agent_id": {"type": "string"},
                 }, "required": ["agent_id"]}),
            Tool(name="do_nothing", description="Take no action this round",
                 parameters={"type": "object", "properties": {}}),
        ]
        return tools

    def publish_events(self) -> list[Event]:
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    def current_engagement(self) -> dict[str, tuple[int, int]]:
        """Return {post_id: (likes, dislikes)} snapshot for the round.

        Used by the engine to feed engagement signals into belief updates.
        """
        return {pid: (post.likes, post.dislikes) for pid, post in self.posts.items()}

    def tick(self) -> None:
        self.current_round += 1
        for post_id, post in self.posts.items():
            total = post.likes + post.reposts
            if total >= self.config.viral_threshold and post_id not in self._new_viral:
                self._new_viral.add(post_id)
                self._pending_events.append(Event(
                    source=self.name, type="viral_post",
                    data={"post_id": post_id, "text": post.text, "author": post.author_name,
                          "score": total},
                    round=self.current_round,
                ))

    def _handle_create_post(self, agent: Agent, args: dict) -> ActionResult:
        post_id = str(uuid.uuid4())
        post = Post(id=post_id, author_id=agent.id, author_name=agent.name,
                    text=args.get("text", ""), created_round=self.current_round)
        self.posts[post_id] = post
        return ActionResult(success=True, data={"post_id": post_id})

    def _handle_reply(self, agent: Agent, args: dict) -> ActionResult:
        parent_id = args.get("post_id", "")
        if parent_id not in self.posts:
            return ActionResult(success=False, data={"error": "Post not found"})
        post_id = str(uuid.uuid4())
        reply = Post(id=post_id, author_id=agent.id, author_name=agent.name,
                     text=args.get("text", ""), parent_id=parent_id,
                     created_round=self.current_round)
        self.posts[post_id] = reply
        return ActionResult(success=True, data={"post_id": post_id})

    def _handle_vote(self, agent: Agent, args: dict) -> ActionResult:
        post_id = args.get("post_id", "")
        value = args.get("value", 1)
        if post_id not in self.posts:
            return ActionResult(success=False, data={"error": "Post not found"})
        post = self.posts[post_id]
        if agent.id in post.voters:
            return ActionResult(success=False, data={"error": "Already voted"})
        post.voters.add(agent.id)
        if value > 0:
            post.likes += 1
        else:
            post.dislikes += 1
        return ActionResult(success=True, data={"post_id": post_id})

    def _handle_repost(self, agent: Agent, args: dict) -> ActionResult:
        post_id = args.get("post_id", "")
        if post_id not in self.posts:
            return ActionResult(success=False, data={"error": "Post not found"})
        self.posts[post_id].reposts += 1
        return ActionResult(success=True, data={"post_id": post_id})

    def _handle_follow(self, agent: Agent, args: dict) -> ActionResult:
        target_id = args.get("agent_id", "")
        if agent.id not in self.follows:
            self.follows[agent.id] = set()
        self.follows[agent.id].add(target_id)
        return ActionResult(success=True, data={"followed": target_id})

    def _handle_noop(self, agent: Agent, args: dict) -> ActionResult:
        return ActionResult(success=True, data={})

    def _rank_feed(self, agent_id: str) -> list[Post]:
        top_level = [p for p in self.posts.values() if p.parent_id is None]
        if not top_level:
            return []
        followed = self.follows.get(agent_id, set())
        max_round = max((p.created_round for p in top_level), default=0) or 1
        scored = []
        for post in top_level:
            recency = 1.0 - (max_round - post.created_round) / max(max_round, 1)
            popularity = math.log1p(post.likes + post.reposts)
            relevance = 1.0 if post.author_id in followed else (1.0 - self.config.echo_chamber_strength)
            score = (self.config.recency_weight * recency
                     + self.config.popularity_weight * popularity
                     + self.config.relevance_weight * relevance)
            scored.append((score, post))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [post for _, post in scored]
