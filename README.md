# Alerta Bilhetes Sporting CP

Monitorização gratuita de **todos os eventos anunciados em `openGames`** (futebol e modalidades) com GitHub Actions, Telegram e GitHub Pages.

- **API:** https://tickets.sporting.pt/api/match/allopengames
- **Site:** https://filandre1.github.io/-sporting-tickets-telegram/
- **Eventos (JSON):** https://filandre1.github.io/-sporting-tickets-telegram/games.json
- **Alterações (JSON):** https://filandre1.github.io/-sporting-tickets-telegram/history.json

## Como funciona

`.github/workflows/monitor.yml` consulta a API **de hora a hora, ao minuto :17 (hora de Lisboa)**. O GitHub Actions pode atrasar ou omitir execuções; não há garantia de monitorização em tempo real.

`sporting_data.py` centraliza o acesso HTTP (cabeçalhos, validação de `success=true` e `data.openGames`) e normaliza eventos **sem limitar a 30 dias**, incluindo todas as modalidades. Conserva identificador, data/hora, competição, equipas, `eventName`, `soldOut`, `allowSale`, `allowOnGoingSales`, `disabledReasonDesc`, `member`, `public`, `eclectic` e `isDateConfirmed`.

`monitor.py` compara por `id` com o último `baseline.json` válido, enviando alerta apenas para eventos novos, alterações de estado/data ou eventos que **deixaram de constar em `openGames`** (não significa cancelamento). Não gera alertas por falhas de API. O primeiro ciclo com o novo formato migra a referência de futebol para todas as modalidades **sem anunciar novidades artificiais**.

O **resumo diário** é enviado no primeiro ciclo a partir das **08h00 de Lisboa**. A hora efetiva depende da execução GitHub Actions. O histórico de alterações confirmadas fica em `history.json` (até 2000 entradas). A gravação é efetuada só depois de a API do Telegram aceitar as mensagens; um erro de commit posterior pode provocar reenvio.

`.github/workflows/pages.yml` consulta a API e publica o site e `games.json` a cada hora, ao minuto :37. Publica também `history.json`. Quando a consulta falha, usa `baseline.json` como recurso, mostrando claramente `stale: true`, data da última leitura e `scope`. Dados de recurso **não devem ser interpretados como alterações recentes**.

### Formato publicado

- `games.json`: `games`, `fetchedAt`, `generatedAt`, `stale`, `source`, `scope` e `note`.
- `history.json`: `events` (timestamp `observedAt`, tipo, evento, `id`, alterações de campos ANTES/DEPOIS), `updatedAt`, `generatedAt`.
- `baseline.json`: referência persistida do monitor de Telegram, `version: 2`, `scope: all_open_games` e `jogos`.

**Nota:** o `history.json` regista alterações detetadas nas execuções do monitor, não todas as alterações momentâneas que possam acontecer entre consultas. `games.json` é um retrato da última publicação, não uma consulta em tempo real. Os campos de venda são indicadores da API, não garantias de que o utilizador pode concluir uma compra.

## Configurar

1. Em [Settings → Pages](https://github.com/filandre1/-sporting-tickets-telegram/settings/pages), escolhe **GitHub Actions** como fonte.
2. Em [Secrets de Actions](https://github.com/filandre1/-sporting-tickets-telegram/settings/secrets/actions), configura `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`. Nunca publiques estes valores no repositório.
3. Executa manualmente [Bilheteira Sporting CP](https://github.com/filandre1/-sporting-tickets-telegram/actions/workflows/monitor.yml) e [Publicar Alerta Bilhetes](https://github.com/filandre1/-sporting-tickets-telegram/actions/workflows/pages.yml) para testar.
4. Confirma se os ficheiros JSON publicados têm `stale: false` e o horário `fetchedAt` recente.

## Testes locais

Requer Python 3.12+ e `requests`.

```bash
python -m pip install requests
python -m unittest -v test_monitor
python -m unittest discover -s pages -p 'test_*.py' -v
python pages/build_site.py --offline
python -m http.server 8000 --directory _site
```

O modo offline usa o último `baseline.json`. Os testes não contactam o Telegram nem a API do Sporting.

## Custos e limitações

GitHub Pages e GitHub Actions podem funcionar gratuitamente neste repositório público, dentro dos limites do plano. O endpoint da bilheteira pode ter indisponibilidades ou limites de acesso. Este projeto é independente e não oficial do Sporting CP.
