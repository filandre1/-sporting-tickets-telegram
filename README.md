# Bilheteira Sporting CP — Alertas no Telegram

Monitor de bilhetes de futebol do Sporting CP (https://tickets.sporting.pt).

## O que faz

- Verifica a API `allopengames` de **30 em 30 minutos** (GitHub Actions, cron em UTC; a execução pode atrasar).
- Filtra os jogos de futebol dos próximos 30 dias e compara-os com `baseline.json`.
- Envia alertas ao Telegram se surgirem **novos jogos** ou **alterações** (`soldOut`, `public`, `allowSale`, data, adversário, etc.).
- Envia **um resumo diário**, na primeira verificação após as 11:00 UTC (11:00 de inverno / 12:00 de verão em Lisboa).
- Não envia mensagens de "sem novidades" em cada verificação.
- Atualiza `baseline.json` apenas quando existem mudanças ou quando regista o resumo diário.

Se a bilheteira não responder, a execução do GitHub Actions falha e tenta enviar um aviso por Telegram. Se o Telegram falhar, o estado anterior não é substituído para que o aviso possa ser repetido.

## Configuração

Secrets do repositório (Settings → Secrets and variables → Actions):
- `TELEGRAM_BOT_TOKEN` — token do bot criado no @BotFather
- `TELEGRAM_CHAT_ID` — ID do chat que recebe os alertas

O workflow precisa de permissão `contents: write` para atualizar o baseline.

## Testar manualmente

Actions → "Bilheteira Sporting CP" → Run workflow. Uma execução manual sem novidades e fora da janela de resumo **não envia mensagem**, por definição.

Nota: os horários de `schedule` do GitHub Actions são aproximados e podem sofrer atrasos.
