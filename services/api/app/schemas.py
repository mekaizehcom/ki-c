import uuid

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginStep1Response(BaseModel):
    status: str  # "totp_required" | "totp_enroll"
    challenge_id: str
    enroll_uri: str | None = None  # present when the user must first enroll TOTP


class TotpVerifyRequest(BaseModel):
    challenge_id: str
    code: str = Field(min_length=6, max_length=8)


class SessionResponse(BaseModel):
    status: str = "ok"
    user: "UserOut"


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    role: str
    status: str
    totp_enabled: bool
    allowed_channels: list[str]

    class Config:
        from_attributes = True


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    display_name: str = ""
    password: str = Field(min_length=8)
    role: str = "user"
    allowed_channels: list[str] = ["web", "swisschat"]


class MessageOut(BaseModel):
    detail: str


SessionResponse.model_rebuild()
