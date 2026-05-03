from http import HTTPStatus

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.schemas import Message
from .routes import (
    auth,
    criticidade,
    dist,
    etl,
    pipeline,
    pt_and_pnt,
    tam,
    users,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, substitua "*" pelo seu domínio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(auth.router)
app.include_router(criticidade.router, prefix='/etl')
app.include_router(etl.router, prefix='/etl')
app.include_router(pipeline.router, prefix='/pipeline')
app.include_router(pt_and_pnt.router)
app.include_router(dist.router, prefix='/dist')
app.include_router(tam.router)


@app.get('/', status_code=HTTPStatus.OK, response_model=Message)
def read_root():
    return {'message': 'Hello World'}
