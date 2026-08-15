from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from prometheus_client import make_asgi_app
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agent.memory import session_memory
from src.agent.service import AgentService
from src.core.config import settings
from src.core.logging import configure_logging
from src.db.base import Base
from src.db.session import engine, get_db
from src.eval.runner import run_evaluation
from src.models.run import AgentRun
from src.schemas.agent import (
    AgentRequest,
    AgentResponse,
    AgentRunRead,
    EvalResponse,
)

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

app.mount(
    "/metrics",
    make_asgi_app(),
)


@app.get("/health")
def health():
    return {
        "status": "ok",
    }


@app.get("/ready")
def ready(
    db: Session = Depends(get_db),
):
    db.execute(
        select(1)
    )

    return {
        "status": "ready",
    }


@app.post(
    "/api/v1/agent/run",
    response_model=AgentResponse,
)
def run_agent(
    payload: AgentRequest,
    db: Session = Depends(get_db),
):
    session_id = (
        payload.session_id
        or str(uuid4())
    )

    context = session_memory.get_context(
        session_id
    )

    try:
        run = AgentService().run(
            db,
            payload.message,
            context=context,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    session_memory.add_turn(
        session_id=session_id,
        message=payload.message,
        answer=run.answer,
        tool_used=run.tool_used,
        tool_output=run.tool_output,
    )

    return AgentResponse(
        run_id=run.id,
        session_id=session_id,
        answer=run.answer,
        tool_used=run.tool_used,
        tool_input=run.tool_input,
        tool_output=run.tool_output,
        latency_ms=run.latency_ms,
    )


@app.delete(
    "/api/v1/sessions/{session_id}",
)
def clear_session(
    session_id: str,
):
    cleared = session_memory.clear(
        session_id
    )

    return {
        "session_id": session_id,
        "cleared": cleared,
    }


@app.get(
    "/api/v1/agent/runs",
    response_model=list[AgentRunRead],
)
def list_runs(
    limit: int = Query(
        50,
        ge=1,
        le=500,
    ),
    db: Session = Depends(get_db),
):
    return list(
        db.scalars(
            select(AgentRun)
            .order_by(
                AgentRun.created_at.desc()
            )
            .limit(limit)
        ).all()
    )


@app.get(
    "/api/v1/agent/runs/{run_id}",
    response_model=AgentRunRead,
)
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
):
    run = db.get(
        AgentRun,
        run_id,
    )

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="Run not found",
        )

    return run


@app.post(
    "/api/v1/eval/run",
    response_model=EvalResponse,
)
def evaluate(
    db: Session = Depends(get_db),
):
    return run_evaluation(db)