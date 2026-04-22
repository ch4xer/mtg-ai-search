from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: EmailStr


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    code: str


class ChangePasswordRequest(BaseModel):
    code: str
    new_password: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict

