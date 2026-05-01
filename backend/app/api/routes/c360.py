"""C360 routes: Reference metadata + Ask C360 (NL->SQL) + safe SQL runner."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.c360_service import C360RedshiftService

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/c360", tags=["c360"])


class RunSqlRequest(BaseModel):
    sql: str = Field(..., min_length=1)
    limit: int = Field(default=200, ge=1, le=5000)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3)
    history: List[Dict[str, Any]] = Field(default_factory=list)


def _extract_sql(answer_text: str) -> Optional[str]:
    if "<sql>" in answer_text and "</sql>" in answer_text:
        return answer_text.split("<sql>", 1)[1].split("</sql>", 1)[0].strip()
    return None


def _ollama_chat(system: str, messages: List[Dict[str, str]], max_tokens: int) -> str:
    payload = {
        "model": settings.ollama_model,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": settings.ollama_temperature,
        },
    }
    with httpx.Client(timeout=300.0) as client:
        resp = client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        # Ollama returns { message: { content } }
        return (data.get("message", {}) or {}).get("content", "").strip()


@router.get("/schema")
def get_reference_schema():
    """
    Return allowlisted C360 table schemas from Redshift information_schema.
    Intended for the Reference page.
    """
    service = C360RedshiftService()
    return {
        "allowlisted_tables": sorted(service.allowed_tables),
        "schema": service.get_allowlisted_schema(),
    }


@router.post("/run-sql")
def run_sql(request: RunSqlRequest):
    """
    Read-only allowlisted SQL runner for C360 marts.
    Intended for Explorer-like usage by the Reference/Ask pages.
    """
    service = C360RedshiftService()
    try:
        result = service.execute_read_query(request.sql, request.limit)
        return {
            "columns": result.columns,
            "rows": result.rows,
            "row_count": result.row_count,
            "truncated": result.truncated,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("C360 query failed", error=str(e))
        raise HTTPException(status_code=500, detail="Query execution failed")


@router.post("/chat")
def ask_c360(request: ChatRequest):
    """
    NL->SQL + governed execution against allowlisted C360 marts.

    Behavior mirrors `c360-leadership-frontend/scripts/chat_api.py`:
    - redact PII in input/output (best-effort)
    - optionally run SQL emitted in <sql> tags
    - anonymize SQL results (drop email/phone; customer_id -> anon_id)
    """
    service = C360RedshiftService()

    # Redact PII in question + history before sending to LLM
    redacted_question, input_pii = service.redact_pii_text(request.question)

    redacted_history: List[Dict[str, str]] = []
    for h in (request.history or [])[-6:]:
        role = str(h.get("role", "user"))
        content = str(h.get("content", ""))
        content_redacted, _ = service.redact_pii_text(content)
        redacted_history.append({"role": role, "content": content_redacted})

    # Provide a compact schema policy to the LLM (authoritative allowlist)
    allowlist_lines = "\n".join(f"- {t}" for t in sorted(service.allowed_tables))
    system_prompt = f"""You are an expert data analyst for C360 running on Amazon Redshift.

YOU MUST FOLLOW THESE RULES:
1) Only generate SELECT queries (or WITH ... SELECT). Never write DDL/DML.
2) Only query the allowlisted tables below. Always qualify tables with schema.
3) Never select PII columns (email, phone). Never return customer_id. Use aggregates where possible.
4) Keep queries efficient: add LIMIT 20 by default unless the question is clearly aggregate.

ALLOWLISTED TABLES:
{allowlist_lines}

When you need SQL, wrap it in <sql>...</sql> tags. Otherwise answer directly.
Keep final business answer concise (2-5 sentences)."""

    messages = list(redacted_history)
    messages.append({"role": "user", "content": redacted_question})

    try:
        answer_text = _ollama_chat(system_prompt, messages, max_tokens=settings.ollama_max_tokens)
    except Exception as e:
        logger.exception("Ollama call failed", error=str(e))
        raise HTTPException(status_code=503, detail="LLM service unavailable (Ollama)")

    sql_query = _extract_sql(answer_text)
    sql_results: Optional[List[Dict[str, Any]]] = None

    if sql_query:
        sql_lower = sql_query.lower().strip()
        if not (sql_lower.startswith("select") or sql_lower.startswith("with")):
            return {
                "answer": "I can only run SELECT queries for safety.",
                "sql": sql_query,
                "sql_results": None,
                "pii_redacted": bool(input_pii),
                "cache_hit": False,
            }

        try:
            sql_results = service.execute_read_query_dicts(sql_query, limit=20)
            sql_results, results_redacted = service.redact_results_json(sql_results)
        except ValueError as e:
            return {
                "answer": str(e),
                "sql": sql_query,
                "sql_results": None,
                "pii_redacted": bool(input_pii),
                "cache_hit": False,
            }
        except Exception as e:
            logger.exception("C360 SQL execution failed", error=str(e))
            raise HTTPException(status_code=500, detail="SQL execution failed")

        # Second pass: ask the LLM to interpret results
        followup_messages = messages + [
            {"role": "assistant", "content": answer_text},
            {
                "role": "user",
                "content": f"Here are the SQL results (JSON). Provide a clear, concise business answer based on them.\n\n{sql_results}",
            },
        ]
        try:
            answer_text = _ollama_chat(system_prompt, followup_messages, max_tokens=800)
        except Exception as e:
            logger.exception("Ollama follow-up failed", error=str(e))
            # Still return the raw results if interpretation fails

    answer_text, output_pii = service.redact_pii_text(answer_text)
    pii_redacted = bool(input_pii or output_pii)

    return {
        "answer": answer_text,
        "sql": sql_query,
        "sql_results": sql_results,
        "pii_redacted": pii_redacted,
        "cache_hit": False,
    }

