import json
import re
from dataclasses import dataclass

import httpx

from src.agent.tools import TOOL_DESCRIPTIONS
from src.core.config import settings


@dataclass
class Plan:
    action: str
    arguments: dict
    answer: str | None = None


class Planner:
    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(
            timeout=settings.ollama_timeout_seconds
        )

    def plan(
        self,
        message: str,
        context: str = "",
    ) -> Plan:
        fast_plan = self._fast_plan(message)

        if fast_plan is not None:
            return fast_plan

        if settings.enable_llm:
            try:
                return self._plan_with_ollama(
                    message,
                    context=context,
                )
            except Exception:
                pass

        return self._fallback_plan(message)

    def final_answer(
        self,
        message: str,
        tool_name: str,
        tool_output: dict,
        context: str = "",
    ) -> str:
        if tool_name in {
            "calculator",
            "database_stats",
        }:
            return self._fallback_final_answer(
                tool_name,
                tool_output,
            )

        if tool_name == "document_search":
            if settings.enable_llm:
                try:
                    prompt = (
                        "Answer using only the conversation context "
                        "and tool result. Be concise.\n"
                        f"Conversation context:\n{context}\n"
                        f"Current user request: {message}\n"
                        f"Tool: {tool_name}\n"
                        f"Result: {json.dumps(tool_output)}"
                    )

                    return self._ollama_text(prompt)

                except Exception:
                    pass

        return self._fallback_final_answer(
            tool_name,
            tool_output,
        )

    def contextual_answer(
        self,
        message: str,
        context: str,
    ) -> str:
        if not context:
            return "I do not have enough previous context."

        if settings.enable_llm:
            try:
                prompt = (
                    "Answer the current user request using the "
                    "conversation context below.\n"
                    "Resolve references such as 'it', 'that result', "
                    "'the first result', and 'previous result' from "
                    "the conversation context.\n"
                    "Do not invent information. Be concise.\n\n"
                    f"Conversation context:\n{context}\n\n"
                    f"Current user request: {message}"
                )

                return self._ollama_text(prompt)

            except Exception:
                pass

        return (
            "I could not resolve the follow-up "
            "from the conversation context."
        )

    @staticmethod
    def _fast_plan(
        message: str,
    ) -> Plan | None:
        lower = message.lower().strip()

        database_patterns = [
            "database stats",
            "database statistics",
            "run stats",
            "previous runs",
            "how many runs",
            "agent stats",
            "agent statistics",
            "tool usage",
            "tool usage stats",
            "tool usage statistics",
            "tools used",
            "tool used",
            "which tools",
            "what tools",
            "how many tool",
            "tool calls",
            "tools have been used",
            "tools were used",
        ]
        
        database_usage_query = (
            (
                "tool" in lower
                and "direct" in lower
                and (
                    "run" in lower
                    or "runs" in lower
                    or "statistics" in lower
                    or "stats" in lower
                )
            )
            or (
                "database" in lower
                and (
                    "run" in lower
                    or "runs" in lower
                    or "statistics" in lower
                    or "stats" in lower
                )
            )
            or (
                "how many" in lower
                and (
                    "run" in lower
                    or "runs" in lower
                )
            )
        )

        if (
            database_usage_query
            or any(
                pattern in lower
                for pattern in database_patterns
            )
        ):
            return Plan(
                "database_stats",
                {},
            )

        document_patterns = [
            "search the local documents",
            "search local documents",
            "search documents",
            "find documents",
            "find document",
            "in the documents",
            "from the documents",
            "find in documents",
            "local documents",
            "document search",
        ]

        if any(
            pattern in lower
            for pattern in document_patterns
        ):
            query = _clean_document_query(message)

            return Plan(
                "document_search",
                {
                    "query": query,
                    "top_k": 3,
                },
            )

        expression = _extract_math_expression(
            message
        )

        if expression is not None:
            return Plan(
                "calculator",
                {
                    "expression": expression,
                },
            )

        return None

    def _plan_with_ollama(
        self,
        message: str,
        context: str = "",
    ) -> Plan:
        prompt = (
            "You are a tool-routing conversational agent. "
            "Return ONLY valid JSON.\n"
            "Use the conversation context when the current "
            "message refers to previous results.\n"
            f"Conversation context:\n{context}\n"
            f"Tools: {json.dumps(TOOL_DESCRIPTIONS)}\n"
            '{"action":"calculator",'
            '"arguments":{"expression":"2+2"}}, '
            '{"action":"document_search",'
            '"arguments":{"query":"text"}}, '
            '{"action":"database_stats",'
            '"arguments":{}}, or '
            '{"action":"direct",'
            '"arguments":{},'
            '"answer":"..."}\n'
            f"Current user message: {message}"
        )

        payload = _extract_json(
            self._ollama_text(prompt)
        )

        action = payload.get(
            "action",
            "direct",
        )

        allowed_actions = {
            "calculator",
            "document_search",
            "database_stats",
            "direct",
        }

        if action not in allowed_actions:
            raise ValueError(
                "Unknown action"
            )

        return Plan(
            action,
            payload.get("arguments") or {},
            payload.get("answer"),
        )

    def _ollama_text(
        self,
        prompt: str,
    ) -> str:
        response = self.client.post(
            (
                f"{settings.ollama_base_url.rstrip('/')}"
                "/api/generate"
            ),
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
            },
        )

        response.raise_for_status()

        return str(
            response.json()["response"]
        ).strip()

    @staticmethod
    def _fallback_plan(
        message: str,
    ) -> Plan:
        fast_plan = Planner._fast_plan(
            message
        )

        if fast_plan is not None:
            return fast_plan

        return Plan(
            "direct",
            {},
            (
                "I can answer directly, or use calculator, "
                "document search, and database statistics tools."
            ),
        )

    @staticmethod
    def _fallback_final_answer(
        tool_name: str,
        tool_output: dict,
    ) -> str:
        if tool_name == "calculator":
            return str(
                tool_output["result"]
            )

        if tool_name == "database_stats":
            return (
                f"Total runs: "
                f"{tool_output['total_runs']}; "
                f"tool runs: "
                f"{tool_output['tool_runs']}; "
                f"direct runs: "
                f"{tool_output['direct_runs']}."
            )

        if tool_name == "document_search":
            results = tool_output.get(
                "results",
                [],
            )

            if not results:
                return (
                    "No relevant local document "
                    "was found."
                )

            return (
                f"Top match: "
                f"{results[0]['document']}. "
                f"{results[0]['snippet']}"
            )

        return json.dumps(
            tool_output
        )


def _clean_document_query(
    message: str,
) -> str:
    query = message.strip()

    prefixes = [
        "search the local documents for",
        "search local documents for",
        "search documents for",
        "find documents about",
        "find documents for",
        "find document about",
        "find in documents",
    ]

    lower = query.lower()

    for prefix in prefixes:
        if lower.startswith(prefix):
            query = query[
                len(prefix):
            ].strip(
                " .,:;-"
            )
            break

    return query or message


def _extract_json(
    text: str,
) -> dict:
    try:
        return json.loads(
            text.strip()
        )

    except json.JSONDecodeError:
        match = re.search(
            r"\{.*\}",
            text,
            re.DOTALL,
        )

        if not match:
            raise ValueError(
                "No JSON object found"
            )

        return json.loads(
            match.group(0)
        )


def _extract_math_expression(
    message: str,
) -> str | None:
    normalized = message.lower()

    replacements = {
        "multiplied by": "*",
        "times": "*",
        "divided by": "/",
        "plus": "+",
        "minus": "-",
    }

    for phrase, symbol in replacements.items():
        normalized = normalized.replace(
            phrase,
            symbol,
        )

    matches = re.findall(
        r"[0-9\.\+\-\*\/%\(\)\s]+",
        normalized,
    )

    candidates = [
        match.strip()
        for match in matches
        if re.search(
            r"\d",
            match,
        )
    ]

    if not candidates:
        return None

    expression = max(
        candidates,
        key=len,
    )

    expression = expression.strip()

    # Remove sentence punctuation accidentally captured
    # after a numeric expression, e.g. "3.5 * 2.4."
    expression = re.sub(
        r"(?<=\d)\.(?=\s*$)",
        "",
        expression,
    )

    if not re.search(
        r"[\+\-\*\/%]",
        expression,
    ):
        return None

    return expression