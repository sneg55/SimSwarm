from pydantic import BaseModel


class UserInfo(BaseModel):
    id: int
    email: str

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
