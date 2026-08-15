import json
from pathlib import Path

from src.agent.service import AgentService
from src.db.base import Base
from src.db.session import SessionLocal, engine

EVAL_PATH = Path("data/eval/agent_eval.json")


def validate_tool_execution(tool_name: str | None, tool_output: dict | None) -> bool:
    if tool_name is None:
        return True

    if tool_output is None:
        return False

    if tool_name == "calculator":
        result = tool_output.get("result")
        return isinstance(result, (int, float))

    if tool_name == "document_search":
        results = tool_output.get("results")
        return isinstance(results, list) and len(results) > 0

    if tool_name == "database_stats":
        required_fields = {
            "total_runs",
            "tool_runs",
            "direct_runs",
        }
        return required_fields.issubset(tool_output.keys())

    return False


def run_evaluation(db):
    cases = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    service = AgentService()

    results = []
    tool_correct = 0
    execution_correct = 0
    passed = 0

    for case in cases:
        run = service.run(db, case["message"])

        expected_tool = case.get("expected_tool")

        tool_match = run.tool_used == expected_tool
        tool_correct += int(tool_match)

        execution_match = validate_tool_execution(
            run.tool_used,
            run.tool_output,
        )
        execution_correct += int(execution_match)

        answer_match = bool(run.answer and run.answer.strip())

        case_passed = (
            tool_match
            and execution_match
            and answer_match
        )

        passed += int(case_passed)

        results.append(
            {
                "name": case["name"],
                "expected_tool": expected_tool,
                "actual_tool": run.tool_used,
                "tool_match": tool_match,
                "execution_match": execution_match,
                "answer_match": answer_match,
                "passed": case_passed,
            }
        )

    total = len(cases)

    return {
        "total_cases": total,
        "passed_cases": passed,
        "pass_rate": passed / total if total else 0.0,
        "tool_selection_accuracy": (
            tool_correct / total if total else 0.0
        ),
        "tool_execution_accuracy": (
            execution_correct / total if total else 0.0
        ),
        "results": results,
    }


def main():
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        print(
            json.dumps(
                run_evaluation(db),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()