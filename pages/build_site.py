#!/usr/bin/env python3
"""Gera o site público GitHub Pages, sem backend nem credenciais Telegram."""
import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = Path(__file__).resolve().parent / "public"
DEST = ROOT / "_site"
BASELINE = ROOT / "baseline.json"
API_URL = "https://tickets.sporting.pt/api/match/allopengames"
LISBON = ZoneInfo("Europe/Lisbon")
WINDOW_DAYS = 30
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-PT,pt;q=0.9",
    "Referer": "https://tickets.sporting.pt/",
}
TOKEN = re.compile(r"^[A-Za-z0-9_-]+$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")

def clean(value):
    return str(value or "").strip()[:200]

def parse_date(value):
    if not isinstance(value, str) or not DATE.match(value):
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return d.astimezone(LISBON).replace(tzinfo=None) if d.tzinfo else d
    except ValueError:
        return None

def in_window(value, now=None):
    now = now or datetime.now(LISBON).replace(tzinfo=None)
    d = parse_date(value)
    return d is not None and now <= d <= now + timedelta(days=WINDOW_DAYS)

def football(game):
    modality = game.get("modality")
    name = modality.get("name", "") if isinstance(modality, dict) else modality
    return str(game.get("modalityId")) == "1" or "futebol" in clean(name).lower()

def sport_name(game):
    modality = game.get("modality")
    name = modality.get("name", "") if isinstance(modality, dict) else modality
    return clean(name) or ("Futebol" if football(game) else "Modalidade")

def normalize(raw_games, now=None):
    if not isinstance(raw_games, list):
        raise ValueError("A API não devolveu uma lista de jogos.")
    result = []
    for g in raw_games:
        if not isinstance(g, dict) or not in_window(g.get("date"), now):
            continue
        home = clean(g.get("homeTeam", {}).get("name") if isinstance(g.get("homeTeam"), dict) else "")
        away = clean(g.get("awayTeam", {}).get("name") if isinstance(g.get("awayTeam"), dict) else "")
        token = clean(g.get("token"))
        if not (home and away and TOKEN.fullmatch(token)):
            continue
        result.append({
            "id": clean(g.get("id") or token), "token": token, "date": g["date"][:19],
            "sport": sport_name(g), "football": football(g),
            "competition": clean(g.get("competition")), "home": home, "away": away,
            "soldOut": bool(g.get("soldOut")), "allowSale": bool(g.get("allowSale")),
            "public": bool(g.get("public")), "member": bool(g.get("member")),
            "location": "Casa" if "sporting" in home.lower() else
                        "Fora" if "sporting" in away.lower() else "",
        })
    return sorted(result, key=lambda x: (x["date"], x["id"]))

def fetch_open_games():
    request = Request(API_URL, headers=HEADERS)
    with urlopen(request, timeout=25) as response:
        data = json.load(response)
    raw = data.get("data", {}).get("openGames")
    if not isinstance(raw, list):
        raise ValueError("A resposta da bilheteira não contém openGames.")
    return raw

def from_baseline(path=BASELINE, now=None):
    data = json.loads(path.read_text(encoding="utf-8"))
    result = []
    for j in data.get("jogos", []):
        when = j.get("data")
        if not in_window(when, now):
            continue
        title = clean(j.get("jogo"))
        if " vs " not in title:
            continue
        home, away = title.split(" vs ", 1)
        token = clean(j.get("token"))
        if not TOKEN.fullmatch(token):
            continue
        result.append({
            "id": clean(j.get("id") or token), "token": token, "date": when[:19],
            "sport": "Futebol", "football": True,
            "competition": clean(j.get("competicao")), "home": home, "away": away,
            "soldOut": bool(j.get("soldOut")), "allowSale": bool(j.get("allowSale")),
            "public": bool(j.get("public")), "member": bool(j.get("member")),
            "location": "Casa" if "sporting" in home.lower() else
                        "Fora" if "sporting" in away.lower() else "",
        })
    return sorted(result, key=lambda x: (x["date"], x["id"])), data.get("baseline_registrado_em")

def build(offline=False, destination=DEST):
    destination = Path(destination)
    shutil.copytree(PUBLIC, destination, dirs_exist_ok=True)
    (destination / ".nojekyll").write_text("", encoding="utf-8")

    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    stale = False
    if offline:
        games, fetched = from_baseline()
        stale = True
    else:
        try:
            games = normalize(fetch_open_games())
            fetched = generated
        except (OSError, TimeoutError, ValueError, KeyError) as exc:
            print(f"Bilheteira indisponível ({type(exc).__name__}); a usar baseline.", file=sys.stderr)
            games, fetched = from_baseline()
            stale = True
    data = {
        "games": games, "fetchedAt": fetched,
        "generatedAt": generated, "stale": stale,
        "source": "baseline" if stale else "tickets.sporting.pt",
        "note": ("Dados de recurso: apenas futebol e potencialmente desatualizados."
                 if stale else "Dados recolhidos da bilheteira oficial na última publicação."),
    }
    (destination / "games.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Site gerado: {len(games)} jogos; dados de recurso: {stale}")
    return data

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Usar apenas baseline.json (testes)")
    parser.add_argument("--destination", default=str(DEST))
    args = parser.parse_args()
    build(offline=args.offline, destination=Path(args.destination))
