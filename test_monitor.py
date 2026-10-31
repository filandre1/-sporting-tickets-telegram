"""Testes offline: API simulada, futebol e modalidades, estado e notificações."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import monitor
import sporting_data

LISBON = ZoneInfo("Europe/Lisbon")


def game(id=101, modality="Futebol", **overrides):
    raw = {
        "id": id, "token": f"TOKEN{id}", "date": "2026-11-07T20:30:00",
        "modalityId": 1 if modality == "Futebol" else 3, "modality": modality,
        "homeTeam": {"name": "SPORTING CP"}, "awayTeam": {"name": "ADVERSÁRIO"},
        "competition": "Liga", "allowSale": True, "soldOut": False,
        "member": True, "public": False, "eclectic": False,
        "allowOnGoingSales": True, "disabledReasonDesc": "",
        "isDateConfirmed": True,
    }
    raw.update(overrides)
    return raw


def clock(day, hh):
    instant = datetime.fromisoformat(f"{day}T{hh:02d}:17:00").replace(tzinfo=LISBON)

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)
    return FakeDateTime


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        folder = Path(self.tmp.name)
        self.baseline = folder / "baseline.json"
        self.history = folder / "history.json"
        self.patches = [
            patch.object(monitor, "BASELINE_PATH", self.baseline),
            patch.object(monitor, "HISTORY_PATH", self.history),
            patch.object(monitor, "fetch_open_games", return_value=[
                game(), game(202, "Basquetebol"),
            ]),
            patch.object(monitor, "send_telegram"),
        ]
        values = [p.start() for p in self.patches]
        for p in self.patches:
            self.addCleanup(p.stop)
        self.fetch, self.telegram = values[2:]

    def run_at(self, hh, day="2026-10-31"):
        with patch.object(monitor, "datetime", clock(day, hh)):
            return monitor.main()

    def test_primeira_leitura_sem_alerta_e_resumo_a_partir_das_oito(self):
        self.assertEqual(self.run_at(7), 0)
        self.telegram.assert_not_called()
        base = json.loads(self.baseline.read_text())
        self.assertEqual(base["version"], 2)
        self.assertEqual(base["scope"], "all_open_games")
        self.assertEqual(len(base["jogos"]), 2)
        self.assertEqual(self.run_at(8), 0)
        self.assertEqual(self.run_at(9), 0)
        self.assertEqual(self.telegram.call_count, 1)
        self.assertIn("2 eventos", self.telegram.call_args.args[0])

    def test_campos_e_modalidades_e_historico_sem_duplicacoes(self):
        self.run_at(7)
        self.fetch.return_value = [
            game(soldOut=True, disabledReasonDesc="Esgotado"),
            game(202, "Basquetebol"),
            game(303, "Voleibol", eventName="Sporting x rival"),
        ]
        self.assertEqual(self.run_at(8), 0)
        self.assertEqual(self.telegram.call_count, 2)  # alteração + resumo
        text = self.telegram.call_args_list[0].args[0]
        self.assertIn("soldOut", text)
        self.assertIn("Voleibol", text)
        self.assertEqual(self.run_at(9), 0)
        self.assertEqual(self.telegram.call_count, 2)
        changes = json.loads(self.history.read_text())["events"]
        self.assertEqual(len(changes), 2)
        self.assertEqual({x["type"] for x in changes}, {"added", "updated"})

    def test_id_desaparecido_nao_e_cancelamento(self):
        self.run_at(7)
        self.fetch.return_value = [game()]
        self.run_at(7)
        msg = self.telegram.call_args.args[0]
        self.assertIn("Deixou de constar da lista de jogos abertos", msg)
        self.assertNotIn("cancelado", msg.lower())

    def test_migracao_antiga_nao_cria_novos_artificiais(self):
        self.baseline.write_text(json.dumps({
            "baseline_registrado_em": "2026-10-30T10:00:00+00:00",
            "ultimo_resumo_diario_lisboa": "2026-10-31",
            "jogos": [{"id": 101, "modalidade": "Futebol", "jogo": "A vs B"}],
        }))
        self.assertEqual(self.run_at(10), 0)
        self.telegram.assert_not_called()
        self.assertEqual(json.loads(self.history.read_text())["events"], [])

    def test_falha_api_ou_telegram_preserva_historico(self):
        self.fetch.side_effect = OSError("sem ligação")
        self.assertEqual(self.run_at(7), 1)
        self.assertFalse(self.baseline.exists())
        self.fetch.side_effect = None
        self.telegram.side_effect = OSError("telegram offline")
        self.assertEqual(self.run_at(8), 1)
        self.assertFalse(self.baseline.exists())

    def test_normalizacao_sem_filtro_e_estados(self):
        old = game(401, "Andebol", date="2025-01-01T10:00:00")
        far = game(402, "Voleibol", date="2027-03-01T10:00:00")
        result = sporting_data.normalize_games([old, far])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["sport"], "Andebol")
        self.assertEqual(result[1]["sport"], "Voleibol")

    def test_resposta_incompleta_rejeitada(self):
        with self.assertRaises(ValueError):
            sporting_data.normalize_games([game(), {"id": 2}])
        with self.assertRaises(ValueError):
            sporting_data.normalize_games([game(), game()])


if __name__ == "__main__":
    unittest.main()
