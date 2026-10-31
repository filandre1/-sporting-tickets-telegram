"""Testes offline da publicação, incluindo todas as modalidades e histórico."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pages import build_site as site


def game(id, modality):
    return {
        "id": id, "token": f"TOKEN{id}",
        "date": "2026-12-30T19:00:00",
        "modality": modality, "modalityId": 1 if modality == "Futebol" else 7,
        "homeTeam": {"name": "SPORTING CP"}, "awayTeam": {"name": "RIVAL"},
        "soldOut": False, "allowSale": True, "member": True, "public": False,
        "disabledReasonDesc": "Brevemente disponível",
        "allowOnGoingSales": False,
    }


class StaticSiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.dest = self.folder / "site"
        self.baseline = self.folder / "baseline.json"
        self.history = self.folder / "history.json"

    def test_publicacao_total_com_historico_e_timestamp(self):
        self.history.write_text(json.dumps({
            "version": 1, "updatedAt": "2026-10-31T10:00:00Z",
            "events": [{"type": "updated", "id": "2"}],
        }))
        games = [game(1, "Futebol"), game(2, "Basquetebol"), game(3, "Andebol")]
        with patch.object(site, "fetch_open_games", return_value=games):
            result = site.build(destination=self.dest, baseline_path=self.baseline,
                                history_path=self.history)
        self.assertFalse(result["stale"])
        self.assertEqual(result["scope"], "all_open_games")
        self.assertEqual(len(result["games"]), 3)
        self.assertEqual(result["games"][1]["disabledReasonDesc"], "Brevemente disponível")
        self.assertFalse(result["games"][1]["allowOnGoingSales"])
        self.assertTrue(result["fetchedAt"])
        hist = json.loads((self.dest / "history.json").read_text())
        self.assertEqual(hist["events"][0]["id"], "2")
        self.assertTrue((self.dest / "index.html").exists())
        self.assertTrue((self.dest / ".nojekyll").exists())

    def test_falha_api_marca_baseline_v2_desatualizado(self):
        self.baseline.write_text(json.dumps({
            "version": 2, "scope": "all_open_games",
            "baseline_registrado_em": "2026-10-30T11:00:00Z",
            "jogos": [{"id": "5", "sport": "Voleibol", "football": False,
                       "event": "Sporting vs Rival", "date": "2026-11-01T10:00:00"}],
        }))
        with patch.object(site, "fetch_open_games", side_effect=OSError("sem rede")):
            result = site.build(destination=self.dest, baseline_path=self.baseline,
                                history_path=self.history)
        self.assertTrue(result["stale"])
        self.assertEqual(result["scope"], "all_open_games")
        self.assertEqual(len(result["games"]), 1)
        self.assertEqual(result["fetchedAt"], "2026-10-30T11:00:00Z")
        self.assertEqual(result["source"], "baseline")

    def test_baseline_antigo_so_futebol_sem_falsificar_cobertura(self):
        self.baseline.write_text(json.dumps({
            "baseline_registrado_em": "2026-10-30T11:00:00Z",
            "jogos": [{
                "id": 123, "token": "ABC123", "data": "2026-11-01T10:00:00",
                "jogo": "SPORTING CP vs RIVAL", "competicao": "Liga",
            }],
        }))
        result = site.build(offline=True, destination=self.dest,
                            baseline_path=self.baseline, history_path=self.history)
        self.assertEqual(result["scope"], "football_only")
        self.assertTrue(result["stale"])
        self.assertEqual(result["games"][0]["home"], "SPORTING CP")


if __name__ == "__main__":
    unittest.main()
