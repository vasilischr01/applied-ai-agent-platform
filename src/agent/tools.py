from __future__ import annotations

import ast
import math
import operator
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.run import AgentRun

_ALLOWED_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}

_ALLOWED_UNARY = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_ast(node):
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body)

    if isinstance(node, ast.Constant) and isinstance(
        node.value,
        (int, float),
    ):
        return node.value

    if (
        isinstance(node, ast.BinOp)
        and type(node.op) in _ALLOWED_BINARY
    ):
        return _ALLOWED_BINARY[type(node.op)](
            _eval_ast(node.left),
            _eval_ast(node.right),
        )

    if (
        isinstance(node, ast.UnaryOp)
        and type(node.op) in _ALLOWED_UNARY
    ):
        return _ALLOWED_UNARY[type(node.op)](
            _eval_ast(node.operand)
        )

    raise ValueError("Unsupported expression")


def calculator(expression: str) -> dict:
    if len(expression) > 200:
        raise ValueError(
            "Expression too long"
        )

    result = _eval_ast(
        ast.parse(
            expression,
            mode="eval",
        )
    )

    if (
        isinstance(result, complex)
        or not math.isfinite(
            float(result)
        )
    ):
        raise ValueError(
            "Invalid numeric result"
        )

    return {
        "result": float(result),
    }


DOCUMENTS_DIR = Path(
    "data/documents"
)

_cached_documents: list[
    dict[str, str]
] = []

_cached_embeddings: Any = None
_cache_initialized = False

_cache_lock = Lock()


@lru_cache(maxsize=1)
def _get_embedding_model():
    """
    Lazily load the sentence-transformer model.

    The model is downloaded/initialized only when
    document search is used for the first time.
    """

    from sentence_transformers import (
        SentenceTransformer,
    )

    return SentenceTransformer(
        "all-MiniLM-L6-v2"
    )


def _load_document_cache() -> None:
    global _cached_documents
    global _cached_embeddings
    global _cache_initialized

    documents: list[
        dict[str, str]
    ] = []

    for path in sorted(
        DOCUMENTS_DIR.glob("*.txt")
    ):
        text = path.read_text(
            encoding="utf-8"
        ).strip()

        if text:
            documents.append(
                {
                    "document": path.name,
                    "text": text,
                }
            )

    _cached_documents = documents

    if not documents:
        _cached_embeddings = None
        _cache_initialized = True
        return

    corpus = [
        item["text"]
        for item in documents
    ]

    model = _get_embedding_model()

    _cached_embeddings = model.encode(
        corpus,
        convert_to_tensor=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    _cache_initialized = True


def _ensure_document_cache() -> None:
    global _cache_initialized

    if _cache_initialized:
        return

    with _cache_lock:
        if _cache_initialized:
            return

        _load_document_cache()


def document_search(
    query: str,
    top_k: int = 3,
) -> dict:
    if not query.strip():
        raise ValueError(
            "Search query must not be empty"
        )

    if top_k < 1:
        raise ValueError(
            "top_k must be at least 1"
        )

    _ensure_document_cache()

    if (
        not _cached_documents
        or _cached_embeddings is None
    ):
        return {
            "results": [],
        }

    from sentence_transformers import util

    model = _get_embedding_model()

    query_embedding = model.encode(
        query,
        convert_to_tensor=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    similarities = util.cos_sim(
        query_embedding,
        _cached_embeddings,
    )[0]

    result_count = min(
        top_k,
        len(_cached_documents),
    )

    ranked_indices = (
        similarities.argsort(
            descending=True
        )[:result_count]
    )

    results = []

    for index in ranked_indices:
        i = int(index)

        results.append(
            {
                "document": (
                    _cached_documents[i][
                        "document"
                    ]
                ),
                "score": round(
                    float(
                        similarities[i]
                    ),
                    4,
                ),
                "snippet": (
                    _cached_documents[i][
                        "text"
                    ][:500]
                ),
            }
        )

    return {
        "results": results,
    }


def database_stats(
    db: Session,
) -> dict:
    total = (
        db.scalar(
            select(
                func.count()
            ).select_from(
                AgentRun
            )
        )
        or 0
    )

    tool_runs = (
        db.scalar(
            select(
                func.count()
            )
            .select_from(
                AgentRun
            )
            .where(
                AgentRun.tool_used.is_not(
                    None
                )
            )
        )
        or 0
    )

    return {
        "total_runs": int(
            total
        ),
        "tool_runs": int(
            tool_runs
        ),
        "direct_runs": int(
            total - tool_runs
        ),
    }


TOOL_DESCRIPTIONS = {
    "calculator": {
        "description": (
            "Evaluate arithmetic."
        ),
        "arguments": {
            "expression": "string",
        },
    },
    "document_search": {
        "description": (
            "Search local text documents "
            "using semantic similarity."
        ),
        "arguments": {
            "query": "string",
        },
    },
    "database_stats": {
        "description": (
            "Return aggregate "
            "agent-run statistics."
        ),
        "arguments": {},
    },
}