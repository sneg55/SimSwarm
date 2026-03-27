import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from saas.database import get_session
from saas.billing.ledger import CreditLedger
from saas.billing.credit_packs import get_pack, CREDIT_PACKS
from saas.billing.stripe_service import StripeService
from saas.schemas.billing import (
    BalanceResponse,
    PurchaseRequest,
    PurchaseResponse,
    CreditHistoryEntry,
)
from saas.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


def _get_stripe_service() -> StripeService:
    from saas.main import _app_settings  # lazy import to avoid circular
    return StripeService(
        secret_key=_app_settings.STRIPE_SECRET_KEY,
        webhook_secret=_app_settings.STRIPE_WEBHOOK_SECRET,
        success_url=_app_settings.STRIPE_SUCCESS_URL,
        cancel_url=_app_settings.STRIPE_CANCEL_URL,
    )


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
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if body.pack_id not in CREDIT_PACKS:
        raise HTTPException(status_code=400, detail=f"Unknown pack_id: {body.pack_id}")

    user_id = current_user["user_id"]
    pack = get_pack(body.pack_id)
    stripe_service = _get_stripe_service()

    result = stripe_service.create_checkout_session(
        pack_id=body.pack_id,
        user_id=user_id,
        credits=pack.credits,
        price_cents=pack.price_cents,
    )
    return PurchaseResponse(**result)


@router.post("/webhook", status_code=200)
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    stripe_service = _get_stripe_service()

    try:
        event = stripe_service.verify_webhook(payload=payload, sig_header=sig_header)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    if event.type == "checkout.session.completed":
        stripe_session = event.data.object
        user_id = stripe_session.metadata.get("user_id")
        pack_id = stripe_session.metadata.get("pack_id")
        stripe_session_id = stripe_session.id

        if not user_id or not pack_id:
            logger.warning("Webhook missing user_id or pack_id in metadata: session=%s", stripe_session_id)
            return {"status": "ok"}

        # Validate pack_id against known packs
        try:
            pack = get_pack(pack_id)
        except KeyError:
            logger.warning("Unknown pack_id %r in webhook: session=%s", pack_id, stripe_session_id)
            return {"status": "ok"}

        ledger = CreditLedger(session)

        # Idempotency: skip if already credited
        if await ledger.session_credited(stripe_session_id):
            logger.info("Duplicate webhook for session %s — skipping", stripe_session_id)
            return {"status": "ok"}

        credits = pack.credits  # trust pack definition, not metadata
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
        payment_intent_id = charge.payment_intent
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
