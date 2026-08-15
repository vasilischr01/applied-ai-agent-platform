import json
from collections import OrderedDict, deque
from threading import RLock
from typing import Any


class SessionMemory:
    def __init__(
        self,
        max_turns: int = 6,
        max_sessions: int = 100,
    ):
        self.max_turns = max_turns
        self.max_sessions = max_sessions
        self._sessions: OrderedDict[str, deque[dict[str, Any]]] = (
            OrderedDict()
        )
        self._lock = RLock()

    def add_turn(
        self,
        session_id: str,
        message: str,
        answer: str,
        tool_used: str | None,
        tool_output: dict | None,
    ) -> None:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = deque(
                    maxlen=self.max_turns
                )

            self._sessions.move_to_end(session_id)

            self._sessions[session_id].append(
                {
                    "message": message,
                    "answer": answer,
                    "tool_used": tool_used,
                    "tool_output": tool_output,
                }
            )

            while len(self._sessions) > self.max_sessions:
                self._sessions.popitem(last=False)

    def get_context(
        self,
        session_id: str,
    ) -> str:
        with self._lock:
            turns = list(
                self._sessions.get(
                    session_id,
                    [],
                )
            )

        if not turns:
            return ""

        lines = []

        for turn in turns:
            lines.append(
                f"User: {turn['message']}"
            )
            lines.append(
                f"Assistant: {turn['answer']}"
            )

            if turn["tool_used"]:
                lines.append(
                    f"Tool used: {turn['tool_used']}"
                )

            if turn["tool_output"]:
                output = json.dumps(
                    turn["tool_output"],
                    ensure_ascii=False,
                )

                lines.append(
                    f"Tool result: {output[:2000]}"
                )

        return "\n".join(lines)

    def clear(
        self,
        session_id: str,
    ) -> bool:
        with self._lock:
            return (
                self._sessions.pop(
                    session_id,
                    None,
                )
                is not None
            )


session_memory = SessionMemory()