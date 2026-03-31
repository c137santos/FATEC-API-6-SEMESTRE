from pydantic import BaseModel, HttpUrl

class DownloadRequest(BaseModel):
    url: HttpUrl