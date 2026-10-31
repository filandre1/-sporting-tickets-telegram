"""Acesso e normalização da API oficial de bilhetes do Sporting CP.

Não filtra modalidades nem limita os eventos a 30 dias.
"""
import re
import time
from urllib.request import Request, urlopen

API_URL = "https://tickets.sporting.pt/api/match/allopengames"
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-PT,pt;q=0.9",
    "Referer": "https://tickets.sporting.pt/",
}
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]+$")
FIELDS_TO_MONITOR = (
    "date", "event", "competition", "sport", "soldOut", "allowSale",
    "allowOnGoingSales", "disabledReasonDesc", "member", "public",
    "eclectic", "isDateConfirmed",
)


def fetch_open_games():
    """Só devolve uma resposta completa quando success=true e openGames é lista."""
    import json

    error = None
    for attempt in range(3):
        try:
            with urlopen(Request(API_URL, headers=HTTP_HEADERS), timeout=30) as response:
                payload = json.load(response)
            if not isinstance(payload, dict) or payload.get("success") is not True:
                raise ValueError("A API não confirmou success=true")
            data = payload.get("data")
            games = data.get("openGames") if isinstance(data, dict) else None
            if not isinstance(games, list):
                raise ValueError("A API não devolveu data.openGames como lista")
            return games
        except (OSError, ValueError, KeyError, TypeError) as exc:
            error = exc
            if attempt < 2:
                time.sleep(2)
    raise RuntimeError("Consulta da API falhou após três tentativas") from error


def text_value(value):
    if isinstance(value, dict):
        value = value.get("name") or value.get("pt") or value.get("description") or ""
    return str(value).strip()[:250] if value is not None else ""


def is_football(game):
    name = text_value(game.get("modality"))
    return str(game.get("modalityId")) == "1" or "futebol" in name.casefold()


def normalize_games(raw_games):
    """Preserva todos os eventos; falha em vez de transformar dados inválidos em remoções."""
    if not isinstance(raw_games, list):
        raise ValueError("Lista de jogos inválida")
    result = []
    ids = set()
    for raw in raw_games:
        if not isinstance(raw, dict) or raw.get("id") is None or not raw.get("date"):
            raise ValueError("Evento sem identificador ou data; resposta incompleta")
        event_id = str(raw["id"])
        if event_id in ids:
            raise ValueError("IDs duplicados na resposta da API")
        ids.add(event_id)
        home = text_value(raw.get("homeTeam"))
        away = text_value(raw.get("awayTeam"))
        event = text_value(raw.get("eventName")) or (
            f"{home} vs {away}" if home and away else home or away or f"Evento {event_id}"
        )
        token = text_value(raw.get("token"))
        if not TOKEN_RE.fullmatch(token):
            token = ""
        sport = text_value(raw.get("modality")) or (
            "Futebol" if is_football(raw) else "Modalidade"
        )
        result.append({
            "id": event_id,
            "token": token,
            "date": str(raw["date"]),
            "event": event,
            "sport": sport,
            "football": is_football(raw),
            "competition": text_value(raw.get("competition")),
            "home": home,
            "away": away,
            "soldOut": raw.get("soldOut"),
            "allowSale": raw.get("allowSale"),
            "allowOnGoingSales": raw.get("allowOnGoingSales"),
            "disabledReasonDesc": text_value(raw.get("disabledReasonDesc")),
            "member": raw.get("member"),
            "public": raw.get("public"),
            "eclectic": raw.get("eclectic"),
            "isDateConfirmed": raw.get("isDateConfirmed"),
        })
    return sorted(result, key=lambda g: (g["date"], g["id"]))


def ticket_url(game):
    token = str(game.get("token") or "")
    return "https://tickets.sporting.pt/" + token if TOKEN_RE.fullmatch(token) else "https://tickets.sporting.pt/pt"


def sale_status(game):
    """Não confunde allowSale=True com disponibilidade garantida."""
    if game.get("soldOut") is True:
        return "Esgotado"
    reason = text_value(game.get("disabledReasonDesc"))
    if reason:
        return reason
    if game.get("allowSale") is False:
        return "Venda indisponível"
    if game.get("allowSale") is True:
        return "Venda permitida pela API (confirmar condições no portal)"
    return "Estado não indicado pela API"
