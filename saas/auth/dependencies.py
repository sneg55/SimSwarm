from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from saas.auth.service import decode_token

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Extract and validate JWT from Authorization header.
    Returns dict with 'sub' (user_id as string) and 'email'."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    settings = request.app.state.settings
    try:
        payload = decode_token(credentials.credentials, settings.SECRET_KEY)
        return {"user_id": payload["sub"], "email": payload["email"]}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
