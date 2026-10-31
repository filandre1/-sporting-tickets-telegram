#!/usr/bin/env python3
"""Monitor de TODOS os eventos da API Sporting, com resumos e alertas Telegram."""
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from sporting_data import (
    FIELDS_TO_MONITOR, fetch_open_games, normalize_games, sale_status, ticket_url,
)

ROOT = Path(__file__).resolve().parent
BASELINE_PATH = ROOT / "baseline.json"
HISTORY_PATH = ROOT / "history.json"
LISBON = ZoneInfo("Europe/Lisbon")
SUMMARY_HOUR = 8
HISTORY_LIMIT = 2000


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def diff(current, previous):
    old = {str(g["id"]): g for g in previous}
    new = {str(g["id"]): g for g in current}
    changes = []
    for event_id in sorted(new.keys() - old.keys()):
        changes.append({"type": "added", "id": event_id, "game": new[event_id], "fields": {}})
    for event_id in sorted(old.keys() - new.keys()):
        changes.append({"type": "left_open_games", "id": event_id, "game": old[event_id], "fields": {}})
    for event_id in sorted(new.keys() & old.keys()):
        fields = {
            field: {"before": old[event_id].get(field), "after": new[event_id].get(field)}
            for field in FIELDS_TO_MONITOR
            if old[event_id].get(field) != new[event_id].get(field)
        }
        if fields:
            changes.append({"type": "updated", "id": event_id, "game": new[event_id], "fields": fields})
    return changes


def format_game(game):
    return (
        f"{game.get('sport') or 'Modalidade'} · {game.get('event')}\n"
        f"Data: {game.get('date')} · ID: {game.get('id')}\n"
        f"Estado: {sale_status(game)} · Público: {game.get('public')} · Sócios: {game.get('member')}\n"
        f"{ticket_url(game)}"
    )


def change_message(changes):
    lines = ["🚨 Alterações confirmadas na bilheteira Sporting CP"]
    for item in changes:
        game = item["game"]
        if item["type"] == "added":
            lines.append("🆕 Passou a constar da API:\n" + format_game(game))
        elif item["type"] == "left_open_games":
            lines.append("📤 Deixou de constar da lista de jogos abertos (não implica cancelamento):\n" + format_game(game))
        else:
            details = [
                f"  {name}: {vals['before']!r} → {vals['after']!r}"
                for name, vals in item["fields"].items()
            ]
            lines.append("🔄 Alteração:\n" + format_game(game) + "\n" + "\n".join(details))
    return "\n\n".join(lines)


def daily_message(current):
    lines = [f"🎟️ Resumo diário Sporting CP — {len(current)} eventos em openGames"]
    for g in current:
        lines.append(format_game(g))
    lines.append("Fonte: https://tickets.sporting.pt/api/match/allopengames")
    return "\n\n".join(lines)


def send_telegram(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Secrets TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID em falta")
    # Fragmentar por linha/parágrafo, respeitando limite Telegram, sem cortar URLs por norma.
    chunks, chunk = [], ""
    for line in message.splitlines(keepends=True):
        while len(line) > 4096:
            if chunk:
                chunks.append(chunk)
                chunk = ""
            chunks.append(line[:4096])
            line = line[4096:]
        if len(chunk) + len(line) > 4096:
            chunks.append(chunk)
            chunk = ""
        chunk += line
    if chunk:
        chunks.append(chunk)
    for part in chunks:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": part, "disable_web_page_preview": True},
            timeout=30,
        )
        r.raise_for_status()


def write_json(path, data):
    p = Path(path)
    temporary = p.with_suffix(p.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(p)


def step_summary(status, current=None, changes=None, daily=False):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as stream:
        stream.write(
            f"\n### Verificação Sporting CP\n"
            f"- Estado: {status}\n"
            f"- Eventos da API: {len(current) if current is not None else 'indisponível'}\n"
            f"- Alterações: {len(changes or [])}\n"
            f"- Resumo diário: {'sim' if daily else 'não'}\n"
        )


def main():
    utc_now = datetime.now(timezone.utc)
    today = utc_now.astimezone(LISBON).date().isoformat()
    try:
        current = normalize_games(fetch_open_games())
    except Exception as exc:
        print("Falha na API; baseline preservado:", type(exc).__name__, str(exc))
        traceback.print_exc()
        step_summary("API indisponível")
        return 1

    baseline = load_json(BASELINE_PATH, {})
    # Migração v1 -> v2: o histórico anterior só continha FUTEBOL; não
    # podemos comparar com a lista completa e anunciar modalidades como novas.
    compatible = baseline.get("version") == 2 and baseline.get("scope") == "all_open_games"
    changes = diff(current, baseline.get("jogos", [])) if compatible else []
    last_summary = baseline.get("ultimo_resumo_diario_lisboa")
    if last_summary is None:
        last_summary = baseline.get("ultimo_resumo_diario_utc")
    send_daily = utc_now.astimezone(LISBON).hour >= SUMMARY_HOUR and last_summary != today

    messages = []
    if changes:
        messages.append(change_message(changes))
    if send_daily:
        messages.append(daily_message(current))
    try:
        for message in messages:
            send_telegram(message)
    except Exception as exc:
        print("Falha no Telegram; histórico não atualizado:", type(exc).__name__)
        step_summary("Telegram indisponível", current, changes, send_daily)
        return 1

    if send_daily:
        last_summary = today
    stamp = utc_now.isoformat(timespec="seconds")
    new_baseline = {
        "version": 2,
        "scope": "all_open_games",
        "baseline_registrado_em": stamp,
        "ultimo_resumo_diario_lisboa": last_summary,
        "jogos": current,
    }
    # Registar apenas as mudanças efetivamente notificadas. Uma migração sem
    # histórico compatível inicia nova referência, sem falsas novidades.
    history = load_json(HISTORY_PATH, {"version": 1, "events": []})
    events = history.get("events", [])
    if not isinstance(events, list):
        events = []
    if changes:
        events.extend([
            {
                "observedAt": stamp, "type": c["type"], "id": c["id"],
                "sport": c["game"].get("sport"), "event": c["game"].get("event"),
                "date": c["game"].get("date"), "fields": c["fields"],
            }
            for c in changes
        ])
    if (not compatible or current != baseline.get("jogos")
            or last_summary != baseline.get("ultimo_resumo_diario_lisboa")):
        write_json(BASELINE_PATH, new_baseline)
    if changes or not Path(HISTORY_PATH).exists():
        write_json(HISTORY_PATH, {"version": 1, "updatedAt": stamp, "events": events[-HISTORY_LIMIT:]})
    print(
        f"OK: {len(current)} eventos (todas as modalidades), "
        f"{len(changes)} alterações, resumo={'sim' if send_daily else 'não'}, "
        f"base anterior compatível={'sim' if compatible else 'não'}."
    )
    step_summary("OK", current, changes, send_daily)
    return 0


if __name__ == "__main__":
    sys.exit(main())
