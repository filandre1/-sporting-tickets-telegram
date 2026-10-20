#!/usr/bin/env python3
"""Monitor diário da bilheteira do Sporting CP (futebol) com alertas no Telegram."""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

API_URL = "https://tickets.sporting.pt/api/match/allopengames"
BASELINE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baseline.json")
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
JANELA_DIAS = 30
DIAS_PT = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def fetch_open_games():
    r = requests.get(API_URL, timeout=30)
    r.raise_for_status()
    return r.json()["data"]["openGames"]


def football_next_30_days(games):
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=JANELA_DIAS)
    out = []
    for g in games:
        if g.get("modalityId") != 1 and g.get("modality") != "Futebol":
            continue
        try:
            d = datetime.fromisoformat(g["date"]).replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        if now <= d <= cutoff:
            out.append(g)
    return sorted(out, key=lambda g: g["date"])


def extract(g):
    return {
        "id": g.get("id"),
        "token": g.get("token"),
        "data": g.get("date"),
        "modalidade": "Futebol",
        "competicao": (g.get("competition") or "").strip(),
        "jogo": "%s vs %s" % ((g.get("homeTeam") or {}).get("name", "?"), (g.get("awayTeam") or {}).get("name", "?")),
        "allowSale": g.get("allowSale"),
        "soldOut": g.get("soldOut"),
        "public": g.get("public"),
        "member": g.get("member"),
        "isDateConfirmed": g.get("isDateConfirmed"),
    }


def load_baseline():
    if os.path.exists(BASELINE_PATH):
        with open(BASELINE_PATH) as f:
            return json.load(f)
    return {"baseline_registrado_em": None, "jogos": []}


def diff(current, baseline):
    prev = {j["id"]: j for j in baseline.get("jogos", [])}
    cur = {j["id"]: j for j in current}
    novos = [cur[i] for i in cur if i not in prev]
    alteracoes = []
    campos = ["data", "competicao", "jogo", "allowSale", "soldOut", "public", "member", "isDateConfirmed"]
    for i in cur:
        if i in prev:
            mudancas = [c for c in campos if cur[i].get(c) != prev[i].get(c)]
            if mudancas:
                alteracoes.append((cur[i], mudancas))
    return novos, alteracoes


def estado(j):
    partes = []
    if j["public"]:
        partes.append("sócios + adeptos")
    elif j["member"]:
        partes.append("sócios")
    else:
        partes.append("venda não iniciada")
    if j["soldOut"]:
        partes.append("ESGOTADO")
    if not j["allowSale"]:
        partes.append("venda inativa")
    if not j["isDateConfirmed"]:
        partes.append("data provisória")
    return " | " + " | ".join(partes)


def fmt_jogo(j):
    d = datetime.fromisoformat(j["data"])
    link = "https://tickets.sporting.pt/" + str(j["token"])
    return "%s (%s) %s — %s\n   %s%s\n   %s" % (
        d.strftime("%d/%m"), DIAS_PT[d.weekday()], d.strftime("%H:%M"), j["competicao"],
        j["jogo"], estado(j), link,
    )


def build_message(novos, alteracoes, current):
    linhas = []
    if novos:
        linhas.append("🚨 Novo jogo à venda:")
        for j in novos:
            linhas.append(fmt_jogo(j))
    if alteracoes:
        if novos:
            linhas.append("")
        linhas.append("🔄 Alteração na bilheteira:")
        for j, campos in alteracoes:
            linhas.append(fmt_jogo(j))
            linhas.append("   alterado: " + ", ".join(campos))
    if not novos and not alteracoes:
        linhas.append("ℹ️ Sem novidades na bilheteira de futebol do Sporting CP.")
    linhas.append("")
    linhas.append("Jogos de futebol em aberto nos próximos %d dias: %d" % (JANELA_DIAS, len(current)))
    for j in current:
        est = "esgotado" if j["soldOut"] else ("sócios+adeptos" if j["public"] else "sócios")
        linhas.append("• %s (%s, %s) — %s" % (j["jogo"], j["competicao"], j["data"][:10], est))
    linhas.append("")
    linhas.append("🛒 https://tickets.sporting.pt/")
    return "\n".join(linhas)


def send_telegram(text):
    url = "https://api.telegram.org/bot%s/sendMessage" % TELEGRAM_TOKEN
    while text:
        chunk, text = text[:4096], text[4096:]
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "disable_web_page_preview": True,
        }, timeout=30)
        r.raise_for_status()


def main():
    games = football_next_30_days(fetch_open_games())
    current = [extract(g) for g in games]
    baseline = load_baseline()
    novos, alteracoes = diff(current, baseline)
    msg = build_message(novos, alteracoes, current)
    send_telegram(msg)
    novo_baseline = {
        "baseline_registrado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "jogos": current,
    }
    with open(BASELINE_PATH, "w") as f:
        json.dump(novo_baseline, f, ensure_ascii=False, indent=2)
    print("OK: %d jogos, %d novos, %d alterações." % (len(current), len(novos), len(alteracoes)))


if __name__ == "__main__":
    sys.exit(main())
