"""Testes locais sem ligações reais à bilheteira ou Telegram."""
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

# monitor.py recolhe as variáveis de ambiente na importação.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "12345:TEST_TOKEN_FOR_UNIT_TESTS")
os.environ.setdefault("TELEGRAM_CHAT_ID", "1234567")

import monitor  # noqa: E402

LISBON = ZoneInfo("Europe/Lisbon")


def match(sold_out=False):
    return {
        "id": 22001, "token": "SAFE123ABCD", "date": "2026-10-27T20:15:00",
        "modalityId": 1, "modality": "Futebol",
        "competition": "Taça da Liga",
        "homeTeam": {"name": "SPORTING CP"},
        "awayTeam": {"name": "MARÍTIMO"},
        "allowSale": True, "soldOut": sold_out,
        "public": True, "member": True, "isDateConfirmed": True,
    }


def fake_clock(local_date, hh, mm):
    instant = datetime.strptime(local_date, "%Y-%m-%d").replace(
        hour=hh, minute=mm, tzinfo=LISBON
    )
    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)
    return FakeDatetime


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.baseline = Path(self.tmp.name) / "baseline.json"
        self.step_summary = Path(self.tmp.name) / "step-summary.md"
        self.patches = [
            patch.object(monitor, "BASELINE_PATH", str(self.baseline)),
            patch.object(monitor, "fetch_open_games", return_value=[match()]),
            patch.object(monitor, "send_telegram"),
            patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(self.step_summary)}),
        ]
        results = [p.start() for p in self.patches]
        for p in self.patches:
            self.addCleanup(p.stop)
        self.fetch = results[1]
        self.telegram = results[2]

    def run_at(self, time_str, day="2026-10-24"):
        h, m = map(int, time_str.split(":"))
        with patch.object(monitor, "datetime", fake_clock(day, h, m)):
            return monitor.main()

    def test_seis_verificacoes_so_alertam_uma_vez_por_novidade_e_resumo(self):
        for time_str in ("10:17", "10:47", "11:17", "11:47", "12:17", "12:47"):
            self.assertEqual(self.run_at(time_str), 0)
        self.assertEqual(self.telegram.call_count, 2,
                         "Primeira novidade + resumo diário ao meio-dia")
        first = self.telegram.call_args_list[0].args[0]
        second = self.telegram.call_args_list[1].args[0]
        self.assertIn("Novo jogo", first)
        self.assertIn("Jogos de futebol em aberto", second)
        saved = json.loads(self.baseline.read_text(encoding="utf-8"))
        self.assertEqual(saved["ultimo_resumo_diario_lisboa"], "2026-10-24")
        self.assertEqual(saved["ultimo_resumo_diario_utc"], "2026-10-24")
        report = self.step_summary.read_text(encoding="utf-8")
        self.assertEqual(report.count("### Resultado da verificação"), 6)
        self.assertIn("**Telegram:** Mensagem aceite", report)
        self.assertNotIn(os.environ["TELEGRAM_BOT_TOKEN"], report)

    def test_alteracao_em_verificacao_redundante_nao_e_reenviada(self):
        self.assertEqual(self.run_at("10:17"), 0)
        self.fetch.return_value = [match(sold_out=True)]
        self.assertEqual(self.run_at("10:47"), 0)
        self.assertEqual(self.run_at("11:17"), 0)
        self.assertEqual(self.telegram.call_count, 2)
        self.assertIn("Alteração na bilheteira", self.telegram.call_args_list[1].args[0])

    def test_resumo_ao_meio_dia_de_lisboa_no_inverno(self):
        self.assertEqual(self.run_at("11:47", day="2026-10-26"), 0)
        self.assertEqual(self.telegram.call_count, 1)
        self.assertEqual(self.run_at("12:17", day="2026-10-26"), 0)
        self.assertEqual(self.telegram.call_count, 2)
        self.assertEqual(self.run_at("12:47", day="2026-10-26"), 0)
        self.assertEqual(self.telegram.call_count, 2)

    def test_envio_falhado_nao_avanca_baseline(self):
        self.telegram.side_effect = RuntimeError("Simulação: Telegram indisponível")
        self.assertEqual(self.run_at("10:17"), 1)
        self.assertFalse(self.baseline.exists())
        self.assertIn("FALHOU: Telegram",
                      self.step_summary.read_text(encoding="utf-8"))
        self.telegram.side_effect = None
        self.assertEqual(self.run_at("10:47"), 0)
        self.assertEqual(self.telegram.call_count, 2)

    def test_migracao_baseline_legacy_sem_repetir_resumo(self):
        self.baseline.write_text(json.dumps({
            "baseline_registrado_em": "2026-10-24T11:00:00Z",
            "ultimo_resumo_diario_utc": "2026-10-24",
            "jogos": [monitor.extract(match())],
        }), encoding="utf-8")
        self.assertEqual(self.run_at("12:17"), 0)
        self.telegram.assert_not_called()
        saved = json.loads(self.baseline.read_text(encoding="utf-8"))
        self.assertEqual(saved["ultimo_resumo_diario_lisboa"], "2026-10-24")


if __name__ == "__main__":
    unittest.main()
