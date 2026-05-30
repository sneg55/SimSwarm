"""AI-powered helpers for the simulation wizard."""
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from saas.auth.dependencies import get_current_user

router = APIRouter(prefix="/ai", tags=["ai"])


class GoalGenerateRequest(BaseModel):
    seed_text: str
    category: str  # e.g. "market-reaction", "crisis-response"


class GoalGenerateResponse(BaseModel):
    goal: str


CATEGORY_PROMPTS = {
    "market-reaction": "market reaction, investor sentiment, price narratives, and trading behavior",
    "crisis-response": "crisis response, stakeholder coalitions, media narratives, and public sentiment",
    "policy-impact": "policy impact, regulatory cascades, compliance behavior, and industry lobbying",
    "competitive-dynamics": "competitive dynamics, market repositioning, alliances, and disruption response",
    "public-opinion": "public opinion shifts, platform discourse, influencer coalitions, and demographic divides",
}


@router.post("/generate-goal", response_model=GoalGenerateResponse)
async def generate_goal(
    body: GoalGenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate a specific simulation goal from seed text + category using xAI."""
    api_key = os.getenv("XAI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI goal generation not available")

    category_desc = CATEGORY_PROMPTS.get(body.category, body.category)
    seed_preview = body.seed_text[:2000]

    prompt = (
        f"Based on this document, write ONE specific simulation research question "
        f"focused on {category_desc}.\n\n"
        f"DOCUMENT:\n{seed_preview}\n\n"
        f"Requirements:\n"
        f"- One clear question, 20-40 words\n"
        f"- Reference specific actors/entities from the document by name\n"
        f"- Include a timeframe (e.g. 'over 30 days', 'in the next quarter')\n"
        f"- Be specific enough to guide a social media simulation\n\n"
        f"Return ONLY the question text, nothing else."
    )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        response = client.chat.completions.create(
            model="grok-3-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150,
        )
        goal = response.choices[0].message.content.strip().strip('"')
        return GoalGenerateResponse(goal=goal)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Goal generation failed: {exc}")
