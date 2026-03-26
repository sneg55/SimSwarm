import pytest
from unittest.mock import MagicMock, patch
from saas.billing.stripe_service import StripeService


def test_create_checkout_session():
    service = StripeService(
        secret_key="sk_test_fake",
        webhook_secret="whsec_fake",
        success_url="http://localhost:3000/billing?success=1",
        cancel_url="http://localhost:3000/billing?cancel=1",
    )

    mock_session = MagicMock()
    mock_session.id = "cs_test_123"
    mock_session.url = "https://checkout.stripe.com/pay/cs_test_123"

    with patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create:
        result = service.create_checkout_session(
            pack_id="starter",
            user_id="user-123",
            credits=100,
            price_cents=1900,
        )

    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["mode"] == "payment"
    assert call_kwargs["success_url"] == "http://localhost:3000/billing?success=1"
    assert call_kwargs["cancel_url"] == "http://localhost:3000/billing?cancel=1"
    assert result["session_id"] == "cs_test_123"
    assert result["checkout_url"] == "https://checkout.stripe.com/pay/cs_test_123"


def test_verify_webhook_valid():
    service = StripeService(
        secret_key="sk_test_fake",
        webhook_secret="whsec_fake",
        success_url="http://localhost:3000/billing?success=1",
        cancel_url="http://localhost:3000/billing?cancel=1",
    )

    mock_event = MagicMock()
    mock_event.type = "checkout.session.completed"
    mock_event.data.object.id = "cs_test_123"
    mock_event.data.object.metadata = {"user_id": "user-123", "credits": "100"}

    with patch("stripe.Webhook.construct_event", return_value=mock_event):
        event = service.verify_webhook(payload=b"raw_payload", sig_header="t=123,v1=abc")

    assert event.type == "checkout.session.completed"


def test_verify_webhook_invalid_raises():
    import stripe
    service = StripeService(
        secret_key="sk_test_fake",
        webhook_secret="whsec_fake",
        success_url="http://localhost:3000/billing?success=1",
        cancel_url="http://localhost:3000/billing?cancel=1",
    )

    with patch("stripe.Webhook.construct_event", side_effect=stripe.SignatureVerificationError("bad sig", "sig_header")):
        with pytest.raises(ValueError, match="Invalid webhook signature"):
            service.verify_webhook(payload=b"raw_payload", sig_header="bad_sig")
