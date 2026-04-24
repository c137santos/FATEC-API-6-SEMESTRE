from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, HttpUrl


class Message(BaseModel):
    message: str


class UserSchema(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: int
    username: str
    email: EmailStr
    model_config = ConfigDict(from_attributes=True)


class UserList(BaseModel):
    users: list[UserPublic]


class Token(BaseModel):
    access_token: str
    token_type: str


class DistribuidoraPayload(BaseModel):
    id: str | None
    dist_name: str
    date_gdb: date | None


class SyncDistribuidorasResponse(BaseModel):
    total_recebidas: int
    total_persistidas: int


class DownloadRequest(BaseModel):
    url: HttpUrl


class DecFecRequest(BaseModel):
    url_realizado: HttpUrl
    url_limite: HttpUrl