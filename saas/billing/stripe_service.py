import stripe


class StripeService:
    def __init__(
        self,
        secret_key: str,
        webhook_secret: str,
        success_url: str,
        cancel_url: str,
    ):
        self.webhook_secret = webhook_secret
        self.success_url = success_url
        self.cancel_url = cancel_url
        stripe.api_key = secret_key

    def create_checkout_session(
        self,
        pack_id: str,
        user_id: str,
        credits: int,
        price_cents: int,
    ) -> dict:
        session = stripe.checkout.Session.create(
            mode="payment",
            success_url=self.success_url,
            cancel_url=self.cancel_url,
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"SimSwarm Credits — {pack_id.capitalize()} Pack",
                        },
                        "unit_amount": price_cents,
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "user_id": user_id,
                "pack_id": pack_id,
                "credits": str(credits),
            },
        )
        return {
            "session_id": session.id,
            "checkout_url": session.url,
        }

    def verify_webhook(self, payload: bytes, sig_header: str):
        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=self.webhook_secret,
            )
        except stripe.SignatureVerificationError as exc:
            raise ValueError("Invalid webhook signature") from exc
        return event
