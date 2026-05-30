from pydantic import BaseModel


class UserInfo(BaseModel):
    id: int
    email: str
    email_verified: bool = False

    model_config = {"from_attributes": True}


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    user: UserInfo
    token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str
