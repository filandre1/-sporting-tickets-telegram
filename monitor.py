#!/usr/bin/env python3
"""Monitor diário da bilheteira do Sporting CP (futebol) com alertas no Telegram."""
import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

import requests

API_URL = "https://tickets.sporting.pt/api/match/allopengames"
BASELINE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baseline.json")
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
JANELA_DIAS = 30
DIAS_PT = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

# Alguns sites bloqueiam o User-Agent predefinido do python-requests (403)
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    "Referer": "https://tickets.sporting.pt/",
}


def fetch_open_games():
    last_err = None
    for tentativa in range(3):
        try:
            r = requests.get(API_URL, headers=HTTP_HEADERS, timeout=30)
            r.raise_for_status()
            return r.json()["data"]["openGames"]
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise last_err


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


def build_message(novos, alteracoes, current, incluir_resumo=True):
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
    if incluir_resumo:
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


def guardar_baseline(current, ultimo_resumo_diario_utc):
    novo_baseline = {
        "baseline_registrado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ultimo_resumo_diario_utc": ultimo_resumo_diario_utc,
        "jogos": current,
    }
    with open(BASELINE_PATH, "w") as f:
        json.dump(novo_baseline, f, ensure_ascii=False, indent=2)


def main():
    try:
        games = football_next_30_days(fetch_open_games())
    except Exception as e:  # noqa: BLE001
        # Um erro na consulta deve marcar a execução como falhada no GitHub Actions.
        print("Falha ao consultar a bilheteira:", e)
        traceback.print_exc()
        try:
            send_telegram("⚠️ Monitor Sporting CP: hoje não consegui consultar a bilheteira (%s). Tenta em https://tickets.sporting.pt/" % type(e).__name__)
        except Exception as e2:  # noqa: BLE001
            print("Falha também ao enviar aviso para o Telegram:", e2)
        return 1

    current = [extract(g) for g in games]
    baseline = load_baseline()
    novos, alteracoes = diff(current, baseline)

    agora = datetime.now(timezone.utc)
    hoje_utc = agora.date().isoformat()
    ultimo_resumo = baseline.get("ultimo_resumo_diario_utc")
    if ultimo_resumo is None:
        # Migrar do formato anterior, que já enviava um resumo em cada execução.
        ultimo_resumo = (baseline.get("baseline_registrado_em") or "")[:10] or None
    enviar_resumo = agora.hour >= 11 and ultimo_resumo != hoje_utc

    # Só avisar quando há novidades ou quando chega a altura do resumo diário.
    # Se o Telegram falhar, não avançar o baseline: permite repetir o alerta.
    if novos or alteracoes or enviar_resumo:
        send_telegram(build_message(novos, alteracoes, current, incluir_resumo=enviar_resumo))
        if enviar_resumo:
            ultimo_resumo = hoje_utc
    else:
        print("Sem novidades; nenhuma mensagem enviada ao Telegram.")

    # Evitar commits de 30 em 30 minutos quando nada mudou.
    if (current != baseline.get("jogos", []) or enviar_resumo
            or "ultimo_resumo_diario_utc" not in baseline):
        guardar_baseline(current, ultimo_resumo)
    print("OK: %d jogos, %d novos, %d alterações; resumo diário: %s." % (
        len(current), len(novos), len(alteracoes), "sim" if enviar_resumo else "não"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
