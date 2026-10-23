# Alerta Bilhetes Sporting CP

**Site público gratuito com GitHub Pages + alertas Telegram com GitHub Actions.** Não utiliza Render, Node.js nem servidor pago.

## Site

Depois de ativares o GitHub Pages nas definições do repositório, o endereço esperado é:

**https://filandre1.github.io/-sporting-tickets-telegram/**

> O URL só ficará acessível quando o GitHub Pages estiver configurado e o workflow de publicação terminar com sucesso.

### Arquitetura

- `pages/public/` contém a interface estática, responsiva, com os mesmos filtros **Todos / Futebol / Modalidades** e links para a bilheteira.
- `pages/build_site.py` consulta a API `https://tickets.sporting.pt/api/match/allopengames`, filtra os próximos 30 dias, limpa os campos e gera `_site/games.json`.
- `.github/workflows/pages.yml` publica a versão estática no GitHub Pages após alterações e às **10h35, 11h35 e 12h35 (Europe/Lisbon)**, podendo haver atrasos do GitHub Actions.
- Se a API falhar, a publicação usa os jogos do `baseline.json` anterior (apenas futebol) e assinala explicitamente os dados como desatualizados.
- A página lê o último JSON publicado. **Não é uma bilheteira em tempo real**; o botão Recarregar apenas lê os dados publicados mais recentes.
- `monitor.py` e `.github/workflows/monitor.yml` continuam a gerir os **alertas e resumos no Telegram**, às 10h, 11h e 12h (Lisboa), sem alterações neste processo.
- `baseline.json` mantém o histórico necessário para identificar novos jogos e alterações.

## Publicação gratuita: uma única definição inicial

1. Abre [Settings → Pages](https://github.com/filandre1/-sporting-tickets-telegram/settings/pages).
2. Em **Build and deployment → Source**, seleciona **GitHub Actions**.
3. Abre [Actions → Publicar Alerta Bilhetes (GitHub Pages)](https://github.com/filandre1/-sporting-tickets-telegram/actions/workflows/pages.yml).
4. Clica **Run workflow → main → Run workflow** e confirma se o workflow termina com sucesso.
5. Consulta o endereço indicado em Pages (habitualmente `https://filandre1.github.io/-sporting-tickets-telegram/`).

Se Pages ainda não estiver ativado, o deploy poderá falhar até escolheres **GitHub Actions** como origem em Settings → Pages.

## Manter e testar os alertas Telegram

O GitHub Pages serve apenas ficheiros públicos. **Nunca guardes tokens Telegram em HTML, JavaScript ou JSON exposto publicamente.**

O monitor existente utiliza dois [GitHub Actions Secrets](https://github.com/filandre1/-sporting-tickets-telegram/settings/secrets/actions):

- `TELEGRAM_BOT_TOKEN`: token privado criado com @BotFather.
- `TELEGRAM_CHAT_ID`: identificação do destinatário.

Se já recebes alertas, **não precisas de alterar estes Secrets**. Para testar, abre [Actions → Bilheteira Sporting CP](https://github.com/filandre1/-sporting-tickets-telegram/actions/workflows/monitor.yml) e executa **Run workflow**. Uma execução sem novidades fora da janela de resumo não envia mensagem, por definição.

**Importante:** o site não permite editar o Telegram diretamente pela interface porque é estático; esta configuração é feita na área privada do repositório.

## Testar localmente

Precisas apenas de Python 3.12+.

```bash
python -m unittest discover -s pages -p 'test_*.py' -v
python pages/build_site.py --offline
python -m http.server 8000 --directory _site
```

Abre `http://localhost:8000`. O modo `--offline` usa o histórico local e pode mostrar apenas futebol.

Para gerar com dados atuais:

```bash
python pages/build_site.py
```

## Custos, segurança e limitações

- **Custo de alojamento 0 €**, na modalidade gratuita do GitHub, para este repositório **público**, dentro dos limites de utilização. Sem disco pago, conta de alojamento ou cartão.
- O site tem HTTPS do GitHub Pages. A geração dos dados e os alertas usam GitHub Actions.
- Os dados publicados em `games.json` incluem apenas informações públicas sobre jogos. Segredos Telegram não entram no site.
- O GitHub Actions pode atrasar ou omitir uma execução agendada em períodos de carga.
- `web/` contém a versão anterior para Node.js, **não utilizada no GitHub Pages**; o antigo blueprint `render.yaml` foi retirado para evitar criar um serviço pago por engano.
- Projeto independente, não oficial do Sporting CP.

Documentação: [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) · [GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
