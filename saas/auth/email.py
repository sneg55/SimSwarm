import logging
import secrets

logger = logging.getLogger(__name__)


def generate_token() -> str:
    """Generate a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(32)


def send_verification_email(to_email: str, token: str, base_url: str) -> str:
    """Send verification email. For MVP, just log the link (no SMTP configured)."""
    link = f"{base_url}/api/auth/verify?token={token}"
    # In production, send via SMTP/SendGrid/etc.
    logger.info(f"Verification link for {to_email}: {link}")
    return link


def send_password_reset_email(to_email: str, token: str, base_url: str) -> str:
    """Send password reset email. For MVP, just log the link (no SMTP configured)."""
    link = f"{base_url}/api/auth/reset-password?token={token}"
    # In production, send via SMTP/SendGrid/etc.
    logger.info(f"Password reset link for {to_email}: {link}")
    return link
