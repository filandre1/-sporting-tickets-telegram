# Bilheteira Sporting CP — Alertas no Telegram

Monitor diário da bilheteira de futebol do Sporting CP (https://tickets.sporting.pt).

## O que faz
Todos os dias às 11:05 UTC, consulta a API `allopengames`, filtra os jogos de **futebol** nos próximos 30 dias,
compara com o `baseline.json` do repo e envia alerta para o Telegram:
- 🚨 Novo jogo à venda
- 🔄 Alterações (soldOut, public, allowSale, data, adversário)
- ℹ️ Resumo diário (jogos e estados)

O `baseline.json` é atualizado em cada execução (commit automático).

## Configuração
Secrets do repositório (Settings → Secrets and variables → Actions):
- `TELEGRAM_BOT_TOKEN` — token do bot criado no @BotFather
- `TELEGRAM_CHAT_ID` — id do chat que recebe os alertas

## Testar manualmente
Actions → "Bilheteira Sporting CP" → Run workflow.
