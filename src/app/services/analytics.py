from __future__ import annotations

import re
import sqlite3
import time
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
            channel TEXT DEFAULT 'whatsapp'
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
            session_duration_seconds INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
        CREATE INDEX IF NOT EXISTS idx_conversations_tenant ON conversations(tenant_id);
    """)


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
    ) -> None:
        now = time.time()
        self._conn.execute(
            """INSERT INTO messages
               (conversation_id, role, content, timestamp, char_count, word_count,
                tool_used, tokens_in, tokens_out, response_latency_ms, model_used,
                tenant_id, channel)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                conversation_id, role, content, now,
                len(content), len(content.split()),
                tool_used, tokens_in, tokens_out, response_latency_ms,
                model_used, tenant_id, channel,
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
    ) -> None:
        now = time.time()
        total_turns = len(user_messages) + len(bot_messages)
        frustration = self._compute_frustration(user_messages)
        resolution = self._detect_resolution(user_messages)
        tool_loop = self._detect_tool_loop(tools_called)
        bot_errors = sum(1 for m in bot_messages if ERROR_PATTERNS.search(m))
        avg_latency = int(sum(latencies_ms) / len(latencies_ms)) if latencies_ms else 0

        existing = self._conn.execute(
            "SELECT started_at FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()

        started_at = existing[0] if existing else now
        duration = int(now - started_at)

        self._conn.execute(
            """INSERT OR REPLACE INTO conversations
               (id, tenant_id, channel, started_at, last_message_at, total_turns,
                total_tokens_in, total_tokens_out, tools_called, frustration_score,
                resolution_detected, abandonment_detected, escalation_requested,
                tool_loop_detected, bot_error_count, avg_response_latency_ms,
                session_duration_seconds)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                conversation_id, tenant_id, channel, started_at, now, total_turns,
                total_tokens_in, total_tokens_out, str(tools_called), frustration,
                int(resolution), 0, int(escalation),
                int(tool_loop), bot_errors, avg_latency, duration,
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
                SUM(bot_error_count) as bot_errors
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
        from collections import Counter
        counts = Counter(tools_called)
        return any(v >= 3 for v in counts.values())
