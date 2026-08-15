from prometheus_client import Counter, Histogram

AGENT_RUNS = Counter("agent_runs_total", "Total agent runs", ["status"])
TOOL_CALLS = Counter("agent_tool_calls_total", "Total agent tool calls", ["tool"])
RUN_LATENCY = Histogram("agent_run_latency_seconds", "Agent run latency in seconds")
AGENT_ERRORS = Counter("agent_errors_total", "Total agent errors", ["error_type"])
