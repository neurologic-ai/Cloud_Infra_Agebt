from fastapi import FastAPI
from agent_layer.router import router as agent_router

app = FastAPI(title="Cloud Infra Agent — Notebook Flow")
app.include_router(agent_router, prefix="/api")

@app.get("/healthz")
def healthz():
    return {"status": "ok"}
