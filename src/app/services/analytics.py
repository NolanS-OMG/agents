from __future__ import annotations

import contextlib
import re
import sqlite3
import time
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "analytics.db"

FRUSTRATION_PATTERNS = re.compile(
    r"\b(no me entiendes?|no sirve|no funciona|ya te dije|otra vez|"
    r"no eso no|es incorrecto|está mal|no mam[ea]s|"
    r"a ver si ahora sí|por enésima vez|estoy hart[oa]|"
    r"quiero hablar con (un |una )?(persona|humano|agente|supervisor))\b",
    re.IGNORECASE,
)

RESOLUTION_PATTERNS = re.compile(
    r"\b(gracias|listo|perfecto|ok gracias|ya quedó|excelente|"
    r"eso era todo|muchas gracias|sale|va|órale|chido)\b",
    re.IGNORECASE,
)

ERROR_PATTERNS = re.compile(
    r"\b(no puedo|disculpa|lo siento|no tengo información|"
    r"error|intenta más tarde|problema técnico)\b",
    re.IGNORECASE,
)

PUNCTUATION_ABUSE = re.compile(r"[?!]{3,}")


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp REAL NOT NULL,
            char_count INTEGER NOT NULL,
            word_count INTEGER NOT NULL,
            tool_used TEXT,
            tokens_in INTEGER DEFAULT 0,
            tokens_out INTEGER DEFAULT 0,
            response_latency_ms INTEGER DEFAULT 0,
            model_used TEXT,
            tenant_id TEXT,
            channel TEXT DEFAULT 'whatsapp',
            cost_usd REAL DEFAULT 0.0,
            cached_tokens INTEGER DEFAULT 0,
            reasoning_tokens INTEGER DEFAULT 0,
            finish_reason TEXT,
            generation_id TEXT,
            retry_count INTEGER DEFAULT 0,
            tool_execution_ms INTEGER DEFAULT 0,
            webhook_total_ms INTEGER DEFAULT 0,
            tokens_per_second REAL DEFAULT 0.0,
            context_window_used_pct REAL DEFAULT 0.0,
            ttft_ms INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            tenant_id TEXT,
            channel TEXT,
            started_at REAL,
            last_message_at REAL,
            total_turns INTEGER DEFAULT 0,
            total_tokens_in INTEGER DEFAULT 0,
            total_tokens_out INTEGER DEFAULT 0,
            tools_called TEXT DEFAULT '[]',
            frustration_score INTEGER DEFAULT 0,
            resolution_detected INTEGER DEFAULT 0,
            abandonment_detected INTEGER DEFAULT 0,
            escalation_requested INTEGER DEFAULT 0,
            tool_loop_detected INTEGER DEFAULT 0,
            bot_error_count INTEGER DEFAULT 0,
            avg_response_latency_ms INTEGER DEFAULT 0,
            session_duration_seconds INTEGER DEFAULT 0,
            total_cost_usd REAL DEFAULT 0.0,
            cost_per_turn REAL DEFAULT 0.0,
            turns_to_resolution INTEGER,
            action_executed INTEGER DEFAULT 0,
            action_type TEXT,
            return_user INTEGER DEFAULT 0,
            model_actual TEXT,
            avg_tokens_per_second REAL DEFAULT 0.0,
            max_latency_ms INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
        CREATE INDEX IF NOT EXISTS idx_conversations_tenant ON conversations(tenant_id);
    """)
    _migrate_columns(conn)


def _migrate_columns(conn: sqlite3.Connection) -> None:
    msg_cols = [
        ("cost_usd", "REAL DEFAULT 0.0"),
        ("cached_tokens", "INTEGER DEFAULT 0"),
        ("reasoning_tokens", "INTEGER DEFAULT 0"),
        ("finish_reason", "TEXT"),
        ("generation_id", "TEXT"),
        ("retry_count", "INTEGER DEFAULT 0"),
        ("tool_execution_ms", "INTEGER DEFAULT 0"),
        ("webhook_total_ms", "INTEGER DEFAULT 0"),
        ("tokens_per_second", "REAL DEFAULT 0.0"),
        ("context_window_used_pct", "REAL DEFAULT 0.0"),
        ("ttft_ms", "INTEGER DEFAULT 0"),
    ]
    conv_cols = [
        ("total_cost_usd", "REAL DEFAULT 0.0"),
        ("cost_per_turn", "REAL DEFAULT 0.0"),
        ("turns_to_resolution", "INTEGER"),
        ("action_executed", "INTEGER DEFAULT 0"),
        ("action_type", "TEXT"),
        ("return_user", "INTEGER DEFAULT 0"),
        ("model_actual", "TEXT"),
        ("avg_tokens_per_second", "REAL DEFAULT 0.0"),
        ("max_latency_ms", "INTEGER DEFAULT 0"),
    ]
    for col, dtype in msg_cols:
        with contextlib.suppress(sqlite3.OperationalError):
            conn.execute(f"ALTER TABLE messages ADD COLUMN {col} {dtype}")
    for col, dtype in conv_cols:
        with contextlib.suppress(sqlite3.OperationalError):
            conn.execute(f"ALTER TABLE conversations ADD COLUMN {col} {dtype}")


class AnalyticsStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        _init_db(self._conn)

    def log_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_used: str | None = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        response_latency_ms: int = 0,
        model_used: str | None = None,
        tenant_id: str | None = None,
        channel: str = "whatsapp",
        cost_usd: float = 0.0,
        cached_tokens: int = 0,
        reasoning_tokens: int = 0,
        finish_reason: str | None = None,
        generation_id: str | None = None,
        retry_count: int = 0,
        tool_execution_ms: int = 0,
        webhook_total_ms: int = 0,
        tokens_per_second: float = 0.0,
        context_window_used_pct: float = 0.0,
        ttft_ms: int = 0,
    ) -> None:
        now = time.time()
        self._conn.execute(
            """INSERT INTO messages
               (conversation_id, role, content, timestamp, char_count, word_count,
                tool_used, tokens_in, tokens_out, response_latency_ms, model_used,
                tenant_id, channel, cost_usd, cached_tokens, reasoning_tokens,
                finish_reason, generation_id, retry_count, tool_execution_ms,
                webhook_total_ms, tokens_per_second, context_window_used_pct, ttft_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                conversation_id, role, content, now,
                len(content), len(content.split()),
                tool_used, tokens_in, tokens_out, response_latency_ms,
                model_used, tenant_id, channel, cost_usd, cached_tokens,
                reasoning_tokens, finish_reason, generation_id, retry_count,
                tool_execution_ms, webhook_total_ms, tokens_per_second,
                context_window_used_pct, ttft_ms,
            ),
        )
        self._conn.commit()

    def update_conversation(
        self,
        conversation_id: str,
        user_messages: list[str],
        bot_messages: list[str],
        tools_called: list[str],
        total_tokens_in: int,
        total_tokens_out: int,
        latencies_ms: list[int],
        escalation: bool,
        tenant_id: str | None = None,
        channel: str = "whatsapp",
        cost_usd: float = 0.0,
        model_actual: str | None = None,
        tokens_per_second: float = 0.0,
        action_type: str | None = None,
    ) -> None:
        now = time.time()
        total_turns = len(user_messages) + len(bot_messages)
        frustration = self._compute_frustration(user_messages)
        resolution = self._detect_resolution(user_messages)
        tool_loop = self._detect_tool_loop(tools_called)
        bot_errors = sum(1 for m in bot_messages if ERROR_PATTERNS.search(m))
        avg_latency = int(sum(latencies_ms) / len(latencies_ms)) if latencies_ms else 0
        max_latency = max(latencies_ms) if latencies_ms else 0

        existing = self._conn.execute(
            "SELECT started_at, total_cost_usd FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()

        started_at = existing[0] if existing else now
        prev_cost = existing[1] if existing else 0.0
        total_cost = (prev_cost or 0.0) + cost_usd
        duration = int(now - started_at)
        cost_per_turn = total_cost / total_turns if total_turns > 0 else 0.0

        return_user = 1 if existing else 0
        action_executed = 1 if "ejecutar_accion" in tools_called else 0

        turns_to_res: int | None = None
        if resolution:
            turns_to_res = len(user_messages)

        self._conn.execute(
            """INSERT OR REPLACE INTO conversations
               (id, tenant_id, channel, started_at, last_message_at, total_turns,
                total_tokens_in, total_tokens_out, tools_called, frustration_score,
                resolution_detected, abandonment_detected, escalation_requested,
                tool_loop_detected, bot_error_count, avg_response_latency_ms,
                session_duration_seconds, total_cost_usd, cost_per_turn,
                turns_to_resolution, action_executed, action_type, return_user,
                model_actual, avg_tokens_per_second, max_latency_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                conversation_id, tenant_id, channel, started_at, now, total_turns,
                total_tokens_in, total_tokens_out, str(tools_called), frustration,
                int(resolution), 0, int(escalation),
                int(tool_loop), bot_errors, avg_latency, duration,
                total_cost, cost_per_turn, turns_to_res, action_executed,
                action_type, return_user, model_actual, tokens_per_second, max_latency,
            ),
        )
        self._conn.commit()

    def get_summary(self) -> dict[str, Any]:
        row = self._conn.execute("""
            SELECT
                COUNT(*) as total_conversations,
                SUM(total_turns) as total_turns,
                SUM(total_tokens_in) as tokens_in,
                SUM(total_tokens_out) as tokens_out,
                AVG(frustration_score) as avg_frustration,
                SUM(resolution_detected) as resolutions,
                SUM(escalation_requested) as escalations,
                AVG(avg_response_latency_ms) as avg_latency_ms,
                SUM(tool_loop_detected) as tool_loops,
                SUM(bot_error_count) as bot_errors,
                SUM(total_cost_usd) as total_cost,
                AVG(cost_per_turn) as avg_cost_per_turn,
                AVG(avg_tokens_per_second) as avg_tps,
                AVG(max_latency_ms) as avg_max_latency,
                SUM(action_executed) as actions,
                SUM(return_user) as returns
            FROM conversations
        """).fetchone()

        if not row or not row[0]:
            return {"total_conversations": 0}

        total = row[0]
        return {
            "total_conversations": total,
            "total_turns": row[1] or 0,
            "tokens_in": row[2] or 0,
            "tokens_out": row[3] or 0,
            "avg_frustration_score": round(row[4] or 0, 2),
            "resolution_rate": round((row[5] or 0) / total, 2),
            "escalation_rate": round((row[6] or 0) / total, 2),
            "avg_latency_ms": round(row[7] or 0),
            "tool_loop_rate": round((row[8] or 0) / total, 2),
            "bot_error_rate": round((row[9] or 0) / max(row[1] or 1, 1), 3),
            "total_cost_usd": round(row[10] or 0, 4),
            "avg_cost_per_turn": round(row[11] or 0, 5),
            "avg_tokens_per_second": round(row[12] or 0, 1),
            "avg_max_latency_ms": round(row[13] or 0),
            "action_rate": round((row[14] or 0) / total, 2),
            "return_user_rate": round((row[15] or 0) / total, 2),
        }

    @staticmethod
    def _compute_frustration(user_messages: list[str]) -> int:
        score = 0
        for msg in user_messages:
            if FRUSTRATION_PATTERNS.search(msg):
                score += 2
            if PUNCTUATION_ABUSE.search(msg):
                score += 1
            if len(msg) > 10 and sum(1 for c in msg if c.isupper()) / len(msg) > 0.7:
                score += 1

        for i in range(1, len(user_messages)):
            if SequenceMatcher(
                None, user_messages[i - 1].lower(), user_messages[i].lower()
            ).ratio() > 0.85:
                score += 2

        return score

    @staticmethod
    def _detect_resolution(user_messages: list[str]) -> bool:
        if not user_messages:
            return False
        last_msgs = user_messages[-2:]
        return any(RESOLUTION_PATTERNS.search(m) for m in last_msgs)

    @staticmethod
    def _detect_tool_loop(tools_called: list[str]) -> bool:
        counts = Counter(tools_called)
        return any(v >= 3 for v in counts.values())
