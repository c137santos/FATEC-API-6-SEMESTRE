from pydantic import BaseModel, HttpUrl


class DownloadRequest(BaseModel):
    url: HttpUrl

class DecFecRequest(BaseModel):
    url_realizado: HttpUrl
    url_limite: HttpUrl

