"""Muestra estadísticas de analytics. Uso: uv run python scripts/stats.py"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "analytics.db"


def main() -> None:
    if not DB_PATH.exists():
        print("No hay datos aún. Envía mensajes por WhatsApp o CLI primero.")
        sys.exit(0)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    print("\n" + "=" * 70)
    print("  ANALYTICS - Agente IA")
    print("=" * 70)

    # Resumen general
    row = conn.execute("""
        SELECT
            COUNT(*) as convs,
            SUM(total_turns) as turns,
            SUM(total_tokens_in) as tok_in,
            SUM(total_tokens_out) as tok_out,
            SUM(total_cost_usd) as cost,
            AVG(avg_response_latency_ms) as avg_lat,
            AVG(frustration_score) as avg_frust,
            SUM(resolution_detected) as resolved,
            SUM(escalation_requested) as escalated
        FROM conversations
    """).fetchone()

    total_convs = row["convs"] or 0
    if total_convs == 0:
        print("\n  Sin conversaciones registradas.\n")
        return

    print(f"\n  Conversaciones: {total_convs}")
    print(f"  Turnos totales: {row['turns'] or 0}")
    print(f"  Tokens: {row['tok_in'] or 0:,} in / {row['tok_out'] or 0:,} out")
    print(f"  Costo total: ${row['cost'] or 0:.4f} USD")
    print(f"  Latencia promedio: {row['avg_lat'] or 0:.0f}ms")
    print(f"  Frustración promedio: {row['avg_frust'] or 0:.1f}")
    print(f"  Resoluciones: {row['resolved'] or 0}/{total_convs} ({(row['resolved'] or 0)/total_convs*100:.0f}%)")
    print(f"  Escalaciones: {row['escalated'] or 0}/{total_convs} ({(row['escalated'] or 0)/total_convs*100:.0f}%)")

    # Últimos mensajes
    print(f"\n{'─' * 70}")
    print("  ÚLTIMOS MENSAJES")
    print(f"{'─' * 70}")

    messages = conn.execute("""
        SELECT role, substr(content, 1, 70) as txt, response_latency_ms as lat,
               tokens_in as ti, tokens_out as to_, cost_usd as cost,
               datetime(timestamp, 'unixepoch', 'localtime') as ts
        FROM messages ORDER BY timestamp DESC LIMIT 20
    """).fetchall()

    for msg in reversed(messages):
        role = "🧑" if msg["role"] == "user" else "🤖"
        lat_str = f" ({msg['lat']}ms)" if msg["lat"] else ""
        cost_str = f" ${msg['cost']:.5f}" if msg["cost"] else ""
        print(f"  {role} {msg['ts']}{lat_str}{cost_str}")
        print(f"     {msg['txt']}")

    # Tools usadas
    print(f"\n{'─' * 70}")
    print("  TOOLS MÁS USADAS")
    print(f"{'─' * 70}")

    tools = conn.execute("""
        SELECT tool_used, COUNT(*) as cnt
        FROM messages WHERE tool_used IS NOT NULL AND tool_used != ''
        GROUP BY tool_used ORDER BY cnt DESC LIMIT 10
    """).fetchall()

    if tools:
        for t in tools:
            print(f"  {t['tool_used']}: {t['cnt']} veces")
    else:
        print("  Ninguna tool usada aún.")

    # Conversaciones con más frustración
    print(f"\n{'─' * 70}")
    print("  CONVERSACIONES CON MAYOR FRUSTRACIÓN")
    print(f"{'─' * 70}")

    frustrated = conn.execute("""
        SELECT id, frustration_score, total_turns, resolution_detected,
               session_duration_seconds as dur
        FROM conversations WHERE frustration_score > 0
        ORDER BY frustration_score DESC LIMIT 5
    """).fetchall()

    if frustrated:
        for c in frustrated:
            resolved = "✓" if c["resolution_detected"] else "✗"
            print(f"  {c['id'][:15]}... score={c['frustration_score']} "
                  f"turns={c['total_turns']} resolved={resolved} dur={c['dur']}s")
    else:
        print("  Ninguna conversación con frustración detectada. 🎉")

    # Performance por modelo
    print(f"\n{'─' * 70}")
    print("  RENDIMIENTO POR MODELO")
    print(f"{'─' * 70}")

    models = conn.execute("""
        SELECT model_used, COUNT(*) as cnt,
               AVG(response_latency_ms) as avg_lat,
               AVG(tokens_per_second) as avg_tps,
               SUM(cost_usd) as total_cost,
               AVG(ttft_ms) as avg_ttft
        FROM messages WHERE role='assistant' AND model_used IS NOT NULL
        GROUP BY model_used ORDER BY cnt DESC
    """).fetchall()

    for m in models:
        print(f"  {m['model_used']}")
        print(f"    Mensajes: {m['cnt']} | Latencia: {m['avg_lat']:.0f}ms | "
              f"TTFT: {m['avg_ttft']:.0f}ms | Costo: ${m['total_cost']:.4f}")

    # Actividad por hora
    print(f"\n{'─' * 70}")
    print("  ACTIVIDAD POR HORA (últimos 7 días)")
    print(f"{'─' * 70}")

    hours = conn.execute("""
        SELECT strftime('%H', timestamp, 'unixepoch', 'localtime') as hour,
               COUNT(*) as cnt
        FROM messages WHERE role='user'
          AND timestamp > unixepoch() - 604800
        GROUP BY hour ORDER BY hour
    """).fetchall()

    if hours:
        max_cnt = max(h["cnt"] for h in hours)
        for h in hours:
            bar = "█" * int(h["cnt"] / max_cnt * 30)
            print(f"  {h['hour']}h | {bar} {h['cnt']}")
    else:
        print("  Sin datos suficientes.")

    print(f"\n{'=' * 70}\n")
    conn.close()


if __name__ == "__main__":
    main()
