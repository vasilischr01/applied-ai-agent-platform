from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=5000,
    )
    session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )


class AgentResponse(BaseModel):
    run_id: str
    session_id: str
    answer: str
    tool_used: str | None = None
    tool_input: dict | None = None
    tool_output: dict | None = None
    latency_ms: float


class AgentRunRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: str
    message: str
    answer: str
    tool_used: str | None
    tool_input: dict | None
    tool_output: dict | None
    latency_ms: float
    success: bool
    created_at: datetime


class EvalResponse(BaseModel):
    total_cases: int
    passed_cases: int
    pass_rate: float
    tool_selection_accuracy: float
    tool_execution_accuracy: float
    results: list[dict]
