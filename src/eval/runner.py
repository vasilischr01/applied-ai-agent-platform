from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any

from src.agent.service import AgentService
from src.db.base import Base
from src.db.session import SessionLocal, engine

EVAL_PATH = Path("data/eval/agent_eval.json")
OUTPUT_PATH = Path("artifacts/agent_eval_results.json")

NUMERIC_TOLERANCE = 1e-6


def validate_tool_execution(
    tool_name: str | None,
    tool_output: dict | None,
) -> bool:
    if tool_name is None:
        return True

    if tool_output is None:
        return False

    if tool_name == "calculator":
        result = tool_output.get("result")

        return isinstance(
            result,
            (int, float),
        )

    if tool_name == "document_search":
        results = tool_output.get("results")

        return (
            isinstance(results, list)
            and len(results) > 0
        )

    if tool_name == "database_stats":
        required_fields = {
            "total_runs",
            "tool_runs",
            "direct_runs",
        }

        return required_fields.issubset(
            tool_output.keys()
        )

    return False


def validate_expected_result(
    case: dict[str, Any],
    tool_output: dict | None,
) -> bool:
    """
    Validate deterministic tool results when a case defines
    an expected numeric result.
    """

    if "expected_result" not in case:
        return True

    if not tool_output:
        return False

    actual_result = tool_output.get(
        "result"
    )

    if not isinstance(
        actual_result,
        (int, float),
    ):
        return False

    expected_result = float(
        case["expected_result"]
    )

    return abs(
        float(actual_result)
        - expected_result
    ) <= NUMERIC_TOLERANCE


def validate_required_output_fields(
    case: dict[str, Any],
    tool_output: dict | None,
) -> bool:
    required_fields = case.get(
        "required_output_fields"
    )

    if not required_fields:
        return True

    if not tool_output:
        return False

    return set(
        required_fields
    ).issubset(
        tool_output.keys()
    )


def validate_answer(
    case: dict[str, Any],
    answer: str | None,
) -> bool:
    if not answer:
        return False

    normalized_answer = (
        answer.strip().lower()
    )

    if not normalized_answer:
        return False

    required_terms = case.get(
        "answer_contains",
        [],
    )

    if isinstance(
        required_terms,
        str,
    ):
        required_terms = [
            required_terms
        ]

    if required_terms:
        if not all(
            str(term).lower()
            in normalized_answer
            for term in required_terms
        ):
            return False

    optional_terms = case.get(
        "answer_contains_any",
        [],
    )

    if isinstance(
        optional_terms,
        str,
    ):
        optional_terms = [
            optional_terms
        ]

    if optional_terms:
        if not any(
            str(term).lower()
            in normalized_answer
            for term in optional_terms
        ):
            return False

    return True


def percentile(
    values: list[float],
    percentile_value: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)

    index = (
        len(ordered) - 1
    ) * percentile_value

    lower = int(index)
    upper = min(
        lower + 1,
        len(ordered) - 1,
    )

    fraction = index - lower

    return (
        ordered[lower]
        + (
            ordered[upper]
            - ordered[lower]
        )
        * fraction
    )


def run_evaluation(db) -> dict:
    cases = json.loads(
        EVAL_PATH.read_text(
            encoding="utf-8"
        )
    )

    service = AgentService()

    results = []

    tool_correct = 0
    execution_correct = 0
    answer_correct = 0
    expected_result_correct = 0
    output_fields_correct = 0
    passed = 0

    latencies_ms = []

    for case in cases:
        start = time.perf_counter()

        run = service.run(
            db,
            case["message"],
        )

        latency_ms = (
            time.perf_counter()
            - start
        ) * 1000

        latencies_ms.append(
            latency_ms
        )

        expected_tool = case.get(
            "expected_tool"
        )

        tool_match = (
            run.tool_used
            == expected_tool
        )

        execution_match = (
            validate_tool_execution(
                run.tool_used,
                run.tool_output,
            )
        )

        expected_result_match = (
            validate_expected_result(
                case,
                run.tool_output,
            )
        )

        output_fields_match = (
            validate_required_output_fields(
                case,
                run.tool_output,
            )
        )

        answer_match = (
            validate_answer(
                case,
                run.answer,
            )
        )

        tool_correct += int(
            tool_match
        )

        execution_correct += int(
            execution_match
        )

        expected_result_correct += int(
            expected_result_match
        )

        output_fields_correct += int(
            output_fields_match
        )

        answer_correct += int(
            answer_match
        )

        case_passed = all(
            [
                tool_match,
                execution_match,
                expected_result_match,
                output_fields_match,
                answer_match,
            ]
        )

        passed += int(
            case_passed
        )

        results.append(
            {
                "name": case["name"],
                "expected_tool": (
                    expected_tool
                ),
                "actual_tool": (
                    run.tool_used
                ),
                "tool_match": (
                    tool_match
                ),
                "execution_match": (
                    execution_match
                ),
                "expected_result_match": (
                    expected_result_match
                ),
                "output_fields_match": (
                    output_fields_match
                ),
                "answer_match": (
                    answer_match
                ),
                "latency_ms": round(
                    latency_ms,
                    3,
                ),
                "passed": (
                    case_passed
                ),
            }
        )

    total = len(cases)

    summary = {
        "total_cases": total,
        "passed_cases": passed,
        "pass_rate": (
            passed / total
            if total
            else 0.0
        ),
        "tool_selection_accuracy": (
            tool_correct / total
            if total
            else 0.0
        ),
        "tool_execution_accuracy": (
            execution_correct / total
            if total
            else 0.0
        ),
        "answer_validity_accuracy": (
            answer_correct / total
            if total
            else 0.0
        ),
        "expected_result_accuracy": (
            expected_result_correct
            / total
            if total
            else 0.0
        ),
        "output_schema_accuracy": (
            output_fields_correct
            / total
            if total
            else 0.0
        ),
        "latency_ms": {
            "average": round(
                statistics.mean(
                    latencies_ms
                ),
                3,
            )
            if latencies_ms
            else 0.0,
            "median": round(
                statistics.median(
                    latencies_ms
                ),
                3,
            )
            if latencies_ms
            else 0.0,
            "p95": round(
                percentile(
                    latencies_ms,
                    0.95,
                ),
                3,
            ),
            "max": round(
                max(latencies_ms),
                3,
            )
            if latencies_ms
            else 0.0,
        },
        "results": results,
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            summary,
            indent=2,
        ),
        encoding="utf-8",
    )

    return summary


def main():
    Base.metadata.create_all(
        bind=engine
    )

    with SessionLocal() as db:
        result = run_evaluation(
            db
        )

        print(
            json.dumps(
                result,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()