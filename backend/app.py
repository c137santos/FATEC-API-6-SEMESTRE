from http import HTTPStatus

from fastapi import FastAPI

from .core.schemas import Message
from .listagem_dist import router as listagem_dist
from .routes import auth, etl, users

app = FastAPI()
app.include_router(users.router)
app.include_router(auth.router)
app.include_router(etl.router, prefix='/etl')
app.include_router(listagem_dist.router, prefix='/dist')

app.include_router(users.router)
app.include_router(auth.router)


@app.get('/', status_code=HTTPStatus.OK, response_model=Message)
def read_root():
    return {'message': 'Hello World'}
