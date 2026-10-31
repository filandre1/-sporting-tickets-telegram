#!/usr/bin/env python3
"""Publica todos os eventos da API, data da recolha e histórico de alterações."""
import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sporting_data import fetch_open_games, normalize_games  # noqa: E402

PUBLIC = Path(__file__).resolve().parent / "public"
DEST = ROOT / "_site"
BASELINE = ROOT / "baseline.json"
HISTORY = ROOT / "history.json"


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def from_baseline(path=BASELINE):
    base = read_json(path, {})
    stamp = base.get("baseline_registrado_em")
    if base.get("version") == 2 and base.get("scope") == "all_open_games":
        return base.get("jogos", []), stamp, "all_open_games"
    # Retrocompatibilidade para o baseline antigo (só futebol).
    games = []
    for item in base.get("jogos", []):
        game = {
            "id": str(item.get("id")), "token": item.get("token") or "",
            "date": item.get("data") or "", "sport": "Futebol",
            "football": True, "competition": item.get("competicao") or "",
            "event": item.get("jogo") or "", "soldOut": item.get("soldOut"),
            "allowSale": item.get("allowSale"), "allowOnGoingSales": None,
            "disabledReasonDesc": "", "member": item.get("member"),
            "public": item.get("public"), "eclectic": None,
            "isDateConfirmed": item.get("isDateConfirmed"),
        }
        if " vs " in game["event"]:
            game["home"], game["away"] = game["event"].split(" vs ", 1)
        else:
            game["home"], game["away"] = "", ""
        games.append(game)
    return games, stamp, "football_only"


def build(offline=False, destination=DEST, baseline_path=BASELINE, history_path=HISTORY):
    destination = Path(destination)
    shutil.copytree(PUBLIC, destination, dirs_exist_ok=True)
    (destination / ".nojekyll").write_text("", encoding="utf-8")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    stale = offline
    if not offline:
        try:
            games = normalize_games(fetch_open_games())
            fetched, scope = stamp, "all_open_games"
        except (OSError, TimeoutError, ValueError, KeyError, RuntimeError, TypeError) as exc:
            print(f"API indisponível ({type(exc).__name__}); dados anteriores assinalados como desatualizados.", file=sys.stderr)
            stale = True
    if stale:
        games, fetched, scope = from_baseline(baseline_path)

    output = {
        "games": games, "fetchedAt": fetched, "generatedAt": stamp,
        "stale": stale, "source": "baseline" if stale else "tickets.sporting.pt",
        "scope": scope,
        "note": (
            "Dados históricos, não atualizados nesta publicação."
            if stale else "Dados consultados na API oficial para esta publicação."
        ),
    }
    (destination / "games.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    history = read_json(history_path, {"version": 1, "events": []})
    history_output = {
        "version": 1, "generatedAt": stamp,
        "updatedAt": history.get("updatedAt"),
        "events": history.get("events", []),
        "note": "Alterações confirmadas pelo monitor GitHub Actions, não pela publicação da página.",
    }
    (destination / "history.json").write_text(
        json.dumps(history_output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Site gerado: {len(games)} eventos; âmbito: {scope}; dados desatualizados: {stale}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--destination", default=str(DEST))
    args = parser.parse_args()
    build(offline=args.offline, destination=Path(args.destination))
