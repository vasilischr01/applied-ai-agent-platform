import logging
from time import perf_counter

from sqlalchemy.orm import Session

from src.agent.planner import Planner
from src.agent.tools import calculator, database_stats, document_search
from src.core.metrics import AGENT_ERRORS, AGENT_RUNS, RUN_LATENCY, TOOL_CALLS
from src.models.run import AgentRun

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self, planner: Planner | None = None):
        self.planner = planner or Planner()

    def run(self, db: Session, message: str, context: str = "",) -> AgentRun:
        total_start = perf_counter()

        tool_used = None
        tool_input = None
        tool_output = None

        planning_ms = 0.0
        tool_ms = 0.0
        answer_generation_ms = 0.0

        try:
            planning_start = perf_counter()
            plan = self.planner.plan(message, context=context,)
            planning_ms = (
                perf_counter() - planning_start
            ) * 1000

            if plan.action == "direct":
                if context:
                    answer_start = perf_counter()

                    answer = self.planner.contextual_answer(
                        message,
                        context,
                    )

                    answer_generation_ms = (
                        perf_counter() - answer_start
                    ) * 1000

                else:
                    answer = (
                        plan.answer
                        or "I do not have a direct answer."
                    )
            else:
                tool_used = plan.action
                tool_input = plan.arguments

                tool_start = perf_counter()
                tool_output = self._execute_tool(
                    db,
                    tool_used,
                    tool_input,
                )
                tool_ms = (
                    perf_counter() - tool_start
                ) * 1000

                TOOL_CALLS.labels(
                    tool=tool_used
                ).inc()

                answer_start = perf_counter()
                answer = self.planner.final_answer(
                    message,
                    tool_used,
                    tool_output,
                    context=context,
                )
                answer_generation_ms = (
                    perf_counter() - answer_start
                ) * 1000

            total_ms = (
                perf_counter() - total_start
            ) * 1000

            run = AgentRun(
                message=message,
                answer=answer,
                tool_used=tool_used,
                tool_input=tool_input,
                tool_output=tool_output,
                latency_ms=total_ms,
                success=True,
            )

            db.add(run)
            db.commit()
            db.refresh(run)

            AGENT_RUNS.labels(
                status="success"
            ).inc()

            RUN_LATENCY.observe(
                total_ms / 1000
            )

            logger.info(
                "agent_run_completed",
                extra={
                    "run_id": run.id,
                    "tool_used": tool_used,
                    "planning_ms": round(
                        planning_ms,
                        2,
                    ),
                    "tool_ms": round(
                        tool_ms,
                        2,
                    ),
                    "answer_generation_ms": round(
                        answer_generation_ms,
                        2,
                    ),
                    "total_ms": round(
                        total_ms,
                        2,
                    ),
                },
            )

            return run

        except Exception as exc:
            db.rollback()

            AGENT_RUNS.labels(
                status="error"
            ).inc()

            AGENT_ERRORS.labels(
                error_type=type(exc).__name__
            ).inc()

            logger.exception(
                "agent_run_failed"
            )

            raise

    @staticmethod
    def _execute_tool(
        db: Session,
        name: str,
        args: dict,
    ) -> dict:
        if name == "calculator":
            return calculator(
                args["expression"]
            )

        if name == "document_search":
            return document_search(
                args["query"],
                int(
                    args.get(
                        "top_k",
                        3,
                    )
                ),
            )

        if name == "database_stats":
            return database_stats(db)

        raise ValueError(
            f"Unknown tool: {name}"
        )