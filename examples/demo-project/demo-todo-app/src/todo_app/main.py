from fastapi import FastAPI
from .api.routes import router
from .config import get_settings

app = FastAPI(
    title='Todo API',
    version='1.0.0',
)

app.include_router(router, prefix='/api/v1')


@app.get('/health')
def health_check():
    return {'status': 'ok'}
