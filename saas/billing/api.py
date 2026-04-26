import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.database import get_session
from saas.billing.ledger import CreditLedger
from saas.billing.credit_packs import get_pack, CREDIT_PACKS
from saas.billing.stripe_service import StripeService
from saas.billing.schemas import (
    BalanceResponse,
    PurchaseRequest,
    PurchaseResponse,
    CreditHistoryEntry,
)
from saas.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


def _get_stripe_service(request: Request) -> StripeService:
    settings = request.app.state.settings
    return StripeService(
        secret_key=settings.STRIPE_SECRET_KEY,
        webhook_secret=settings.STRIPE_WEBHOOK_SECRET,
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
    )


@router.get("/packs")
async def list_packs(session: AsyncSession = Depends(get_session)):
    from saas.billing.models import CreditPack as CreditPackModel
    result = await session.execute(
        select(CreditPackModel)
        .where(CreditPackModel.active == True)  # noqa: E712
        .order_by(CreditPackModel.sort_order)
    )
    return [
        {
            "slug": p.slug,
            "name": p.name,
            "credits": p.credits,
            "price_cents": p.price_cents,
            "description": p.description,
        }
        for p in result.scalars()
    ]


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = current_user["user_id"]
    ledger = CreditLedger(session)
    balance = await ledger.get_balance(user_id)
    return BalanceResponse(user_id=user_id, balance=balance)


@router.post("/purchase", response_model=PurchaseResponse)
async def purchase_credits(
    body: PurchaseRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from saas.billing.models import CreditPack as CreditPackModel
    result = await session.execute(
        select(CreditPackModel).where(
            CreditPackModel.slug == body.pack_id,
            CreditPackModel.active == True,  # noqa: E712
        )
    )
    db_pack = result.scalar_one_or_none()

    if db_pack is not None:
        credits = db_pack.credits
        price_cents = db_pack.price_cents
    elif body.pack_id in CREDIT_PACKS:
        # Fallback to hardcoded packs if DB has no matching active entry
        fallback = get_pack(body.pack_id)
        credits = fallback.credits
        price_cents = fallback.price_cents
    else:
        raise HTTPException(status_code=400, detail=f"Unknown pack_id: {body.pack_id}")

    user_id = current_user["user_id"]
    stripe_service = _get_stripe_service(request)

    checkout_result = stripe_service.create_checkout_session(
        pack_id=body.pack_id,
        user_id=user_id,
        credits=credits,
        price_cents=price_cents,
    )
    return PurchaseResponse(**checkout_result)


@router.post("/webhook", status_code=200)
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    stripe_service = _get_stripe_service(request)

    try:
        event = stripe_service.verify_webhook(payload=payload, sig_header=sig_header)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    if event.type == "checkout.session.completed":
        stripe_session = event.data.object
        # Stripe SDK objects raise AttributeError when a field key is absent
        # (e.g. test events sent from the dashboard's "Send test webhook" UI),
        # so read defensively rather than assuming `.metadata` is a dict.
        metadata = getattr(stripe_session, "metadata", None) or {}
        user_id = metadata.get("user_id")
        pack_id = metadata.get("pack_id")
        stripe_session_id = stripe_session.id

        if not user_id or not pack_id:
            logger.warning("Webhook missing user_id or pack_id in metadata: session=%s", stripe_session_id)
            return {"status": "ok"}

        # Validate pack_id and resolve credits from DB (primary) or hardcoded fallback
        from saas.billing.models import CreditPack as CreditPackModel
        pack_result = await session.execute(
            select(CreditPackModel).where(
                CreditPackModel.slug == pack_id,
                CreditPackModel.active == True,  # noqa: E712
            )
        )
        db_pack = pack_result.scalar_one_or_none()
        if db_pack is not None:
            pack_credits = db_pack.credits
        elif pack_id in CREDIT_PACKS:
            pack_credits = CREDIT_PACKS[pack_id].credits
        else:
            logger.warning("Unknown pack_id %r in webhook: session=%s", pack_id, stripe_session_id)
            return {"status": "ok"}

        ledger = CreditLedger(session)

        # Idempotency: skip if already credited
        if await ledger.session_credited(stripe_session_id):
            logger.info("Duplicate webhook for session %s — skipping", stripe_session_id)
            return {"status": "ok"}

        credits = pack_credits  # trust pack definition, not metadata
        payment_intent_id = getattr(stripe_session, "payment_intent", None)
        await ledger.credit(
            user_id=user_id,
            amount=credits,
            description=f"Credit purchase via Stripe session {stripe_session_id}",
            stripe_session_id=stripe_session_id,
            payment_intent_id=payment_intent_id,
        )
        await session.commit()
        logger.info(
            "Credited %d credits to user %s for session %s", credits, user_id, stripe_session_id,
            extra={"event": "credits_added", "user_id": user_id,
                   "credits": credits, "session_id": stripe_session_id},
        )

    elif event.type == "charge.refunded":
        charge = event.data.object
        payment_intent_id = getattr(charge, "payment_intent", None)
        if not payment_intent_id:
            logger.warning("charge.refunded missing payment_intent — ignoring")
            return {"status": "ok"}
        ledger = CreditLedger(session)

        original_credit = await ledger.get_credit_by_payment_intent(payment_intent_id)
        if original_credit is None:
            logger.warning("Refund for unknown payment_intent %s — ignoring", payment_intent_id)
            return {"status": "ok"}

        await ledger.debit(
            user_id=original_credit.user_id,
            amount=original_credit.amount,
            description=f"Refund for payment_intent {payment_intent_id}",
        )
        await session.commit()
        logger.info(
            "Debited %d credits from user %s for refund on payment_intent %s",
            original_credit.amount,
            original_credit.user_id,
            payment_intent_id,
            extra={"event": "refund_processed", "user_id": original_credit.user_id,
                   "credits": original_credit.amount},
        )

    return {"status": "ok"}


@router.get("/history", response_model=list[CreditHistoryEntry])
async def get_history(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = current_user["user_id"]
    ledger = CreditLedger(session)
    entries = await ledger.get_history(user_id)
    return entries
