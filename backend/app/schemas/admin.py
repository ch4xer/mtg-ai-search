from pydantic import BaseModel


class UpdateRoleRequest(BaseModel):
    role: str


class UpdateSettingsRequest(BaseModel):
    anon_hourly_limit: int | None = None
    user_hourly_limit: int | None = None

