from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    status,
)
from prometheus_client import make_asgi_app
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

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
logger = logging.getLogger(__name__)

MAX_REQUEST_BYTES = 64 * 1024
RATE_LIMIT_REQUESTS = 60
RATE_LIMIT_WINDOW_SECONDS = 60

_request_history: dict[
    str,
    deque[float],
] = defaultdict(deque)


class SecurityMiddleware(
    BaseHTTPMiddleware
):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        content_length = (
            request.headers.get(
                "content-length"
            )
        )

        if content_length is not None:
            try:
                request_size = int(
                    content_length
                )

            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": (
                            "Invalid Content-Length "
                            "header"
                        ),
                    },
                )

            if (
                request_size
                > MAX_REQUEST_BYTES
            ):
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            "Request body too large"
                        ),
                    },
                )

        client_host = (
            request.client.host
            if request.client
            else "unknown"
        )

        now = time.monotonic()

        history = _request_history[
            client_host
        ]

        while (
            history
            and now - history[0]
            >= RATE_LIMIT_WINDOW_SECONDS
        ):
            history.popleft()

        if (
            len(history)
            >= RATE_LIMIT_REQUESTS
        ):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        "Too many requests"
                    ),
                },
                headers={
                    "Retry-After": str(
                        RATE_LIMIT_WINDOW_SECONDS
                    ),
                },
            )

        history.append(
            now
        )

        response = await call_next(
            request
        )

        response.headers[
            "X-Content-Type-Options"
        ] = "nosniff"

        response.headers[
            "X-Frame-Options"
        ] = "DENY"

        response.headers[
            "Referrer-Policy"
        ] = "no-referrer"

        response.headers[
            "Permissions-Policy"
        ] = (
            "camera=(), "
            "microphone=(), "
            "geolocation=()"
        )

        response.headers[
            "Cache-Control"
        ] = "no-store"

        return response


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    Base.metadata.create_all(
        bind=engine
    )

    yield


app = FastAPI(
    title=settings.app_name,
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    SecurityMiddleware
)

app.mount(
    "/metrics",
    make_asgi_app(),
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
    }


@app.get("/ready")
def ready(
    db: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        db.execute(
            select(1)
        )

    except SQLAlchemyError as exc:
        logger.exception(
            "readiness_database_check_failed"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Database is not ready"
            ),
        ) from exc

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
) -> AgentResponse:
    session_id = (
        payload.session_id
        or str(uuid4())
    )

    context = (
        session_memory.get_context(
            session_id
        )
    )

    try:
        run = AgentService().run(
            db,
            payload.message,
            context=context,
        )

    except ValueError as exc:
        logger.warning(
            "agent_request_rejected",
            exc_info=exc,
        )

        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "The agent could not "
                "process the request"
            ),
        ) from exc

    except SQLAlchemyError as exc:
        logger.exception(
            "agent_database_error"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Database service "
                "unavailable"
            ),
        ) from exc

    except Exception as exc:
        logger.exception(
            "agent_run_failed"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Internal server error"
            ),
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
) -> dict[str, str | bool]:
    cleared = (
        session_memory.clear(
            session_id
        )
    )

    return {
        "session_id": session_id,
        "cleared": cleared,
    }


@app.get(
    "/api/v1/agent/runs",
    response_model=list[
        AgentRunRead
    ],
)
def list_runs(
    limit: int = Query(
        50,
        ge=1,
        le=500,
    ),
    db: Session = Depends(get_db),
) -> list[AgentRun]:
    try:
        return list(
            db.scalars(
                select(AgentRun)
                .order_by(
                    AgentRun.created_at.desc()
                )
                .limit(limit)
            ).all()
        )

    except SQLAlchemyError as exc:
        logger.exception(
            "list_runs_database_error"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Database service "
                "unavailable"
            ),
        ) from exc


@app.get(
    "/api/v1/agent/runs/{run_id}",
    response_model=AgentRunRead,
)
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> AgentRun:
    try:
        run = db.get(
            AgentRun,
            run_id,
        )

    except SQLAlchemyError as exc:
        logger.exception(
            "get_run_database_error"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Database service "
                "unavailable"
            ),
        ) from exc

    if run is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Run not found",
        )

    return run


@app.post(
    "/api/v1/eval/run",
    response_model=EvalResponse,
)
def evaluate(
    db: Session = Depends(get_db),
) -> EvalResponse:
    try:
        return run_evaluation(
            db
        )

    except Exception as exc:
        logger.exception(
            "evaluation_failed"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Evaluation failed"
            ),
        ) from exc