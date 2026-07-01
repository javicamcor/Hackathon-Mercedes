from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="AI FinOps Proxy - EigenMinds")

app.include_router(router)
