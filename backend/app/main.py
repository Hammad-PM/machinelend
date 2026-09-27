from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine
from app.routers import auth, bookings, machines


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Dev convenience. Switch to Alembic migrations before the first production deploy.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="MachineLend API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router)
app.include_router(machines.router)
app.include_router(bookings.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
