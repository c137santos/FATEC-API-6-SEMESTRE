from datetime import date

from pydantic import BaseModel, HttpUrl


class SyncDistribuidorasRequest(BaseModel):
    initial_url: HttpUrl | None = None


class DistribuidoraPayload(BaseModel):
    id: str | None
    nome_distribuidora: str
    data_gdb: date | None


class SyncDistribuidorasResponse(BaseModel):
    total_recebidas: int
    total_persistidas: int