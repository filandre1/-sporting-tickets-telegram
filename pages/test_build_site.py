"""Testes da geração de site estático, sem API externa nem secrets."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from pages import build_site as site


class StaticSiteTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 23, 14, 0, 0)

    def game(self, **kw):
        data = {
            "id": 123, "token": "ABCDEFG123", "date": "2026-10-25T20:30:00",
            "modalityId": 1, "modality": "Futebol",
            "homeTeam": {"name": "SPORTING CP"},
            "awayTeam": {"name": "MOREIRENSE FC"}, "competition": "Liga",
            "soldOut": False, "allowSale": True, "public": True, "member": True
        }
        data.update(kw)
        return data

    def test_futebol_e_modalidades(self):
        games = site.normalize([
            self.game(),
            self.game(id=456, token="BASKET45", modalityId=3,
                      modality="Basquetebol", date="2026-10-26T19:00:00"),
            self.game(id=789, token="ANTIGO5", date="2026-10-22T14:00:00"),
        ], now=self.now)
        self.assertEqual(len(games), 2)
        self.assertTrue(games[0]["football"])
        self.assertFalse(games[1]["football"])
        self.assertEqual(games[1]["sport"], "Basquetebol")
        self.assertEqual(games[0]["home"], "SPORTING CP")
        self.assertTrue(games[0]["public"])

    def test_rejeitar_tokens_invalidos_e_datas_distantes(self):
        result = site.normalize([
            self.game(token="https://malicioso.example"),
            self.game(token="BEM1234", date="2026-12-10T19:00:00"),
            self.game(token="SAFEXYZ", date="2026-10-27T19:00:00"),
        ], now=self.now)
        self.assertEqual([x["token"] for x in result], ["SAFEXYZ"])

    def test_baseline_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "baseline.json"
            p.write_text(json.dumps({
                "baseline_registrado_em": "2026-10-23T10:00:00+00:00",
                "jogos": [{
                    "id": 77, "token": "ABCD3333", "data": "2026-10-26T18:30:00",
                    "competicao": "Taça", "jogo": "SPORTING CP vs ABC",
                    "public": True, "member": True,
                }],
            }), encoding="utf-8")
            games, stamp = site.from_baseline(p, now=self.now)
            self.assertEqual(len(games), 1)
            self.assertTrue(games[0]["football"])
            self.assertEqual(games[0]["away"], "ABC")
            self.assertEqual(stamp, "2026-10-23T10:00:00+00:00")

    def test_gerador_tem_assets_sem_segredos(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "site"
            payload = site.build(offline=True, destination=destination)
            self.assertTrue((destination / "index.html").exists())
            self.assertTrue((destination / "app.js").exists())
            self.assertTrue((destination / "styles.css").exists())
            self.assertTrue((destination / ".nojekyll").exists())
            self.assertTrue(payload["stale"])
            saved = json.loads((destination / "games.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["source"], "baseline")
            self.assertNotIn("TELEGRAM_BOT_TOKEN", (destination / "games.json").read_text(encoding="utf-8"))
            index = (destination / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="./styles.css"', index)
            self.assertIn('src="./app.js"', index)
            self.assertNotIn('id="token"', index)


if __name__ == "__main__":
    unittest.main()
