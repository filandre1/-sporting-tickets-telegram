# Alerta Bilhetes Sporting — interface web

Reconstrução independente da aplicação pública `alerta-bilhetes-sporting.grok.me`. Não inclui o código-fonte privado original. Integração com a bilheteira oficial e Telegram.

## Funcionalidades

- Jogos em `https://tickets.sporting.pt/api/match/allopengames` e filtros **Todos / Futebol / Modalidades**.
- Consulta da disponibilidade e ligação à bilheteira oficial.
- Configuração Telegram protegida por código de acesso do servidor.
- Token e chat ID armazenados **cifrados com AES-256-GCM** num disco persistente.
- Alertas para jogos novos ou alterações; resumo inicial na primeira verificação.
- Consulta automática todos os dias **dentro da hora das 12h de Lisboa** enquanto o servidor estiver ligado.
- Opção para aviso diário mesmo sem novidades.

## Arranque

Requer Node.js 22+; não existem dependências de terceiros.

```sh
cd web
export ACCESS_CODE='define-um-codigo-secreto-com-mais-de-8-caracteres'
export APP_SECRET='define-uma-chave-aleatoria-com-mais-de-32-caracteres'
npm start
```

Abre `http://localhost:3000`. Guarda o bot/token e ID de chat no formulário e clica **Verificar agora** para receber a primeira mensagem.

## Deploy com HTTPS e disco persistente

Para publicar no Render, consulta o [guia de deploy](DEPLOY-RENDER.md). O ficheiro [`render.yaml`](../render.yaml), na raiz do repositório, configura automaticamente o Web Service de Node.js em Frankfurt, o HTTPS e o SSD persistente. É necessário aprovar a criação de um serviço pago na conta Render.

## Publicação

Publica a pasta `web/` num serviço Node com processo **sempre ligado**, **HTTPS** e **disco persistente**. Comando de arranque: `npm start`; variáveis `ACCESS_CODE`, `APP_SECRET`, `PORT` e, se necessário, `DATA_DIR`. Os ficheiros de configuração são criados em `web/data/` e não devem ser enviados para o GitHub. Mantém o mesmo `APP_SECRET` após reiniciar o serviço.

Sem um processo sempre ativo, a verificação diária pode não acontecer. Uma alternativa mais fiável é usar um agendador externo. O servidor foi concebido para uma única instância.

**Atenção:** este repositório já contém `monitor.py` e um GitHub Actions que envia alertas de futebol. Se ambos forem ativados para o mesmo bot/chat, poderás receber notificações duplicadas. Esta mudança não altera o monitor atual.

## Limitações

- Não é uma cópia do código privado do Grok, mas uma reconstrução funcional da aplicação pública.
- O aspeto foi recriado com base no conteúdo observável; pode não ser pixel-perfect.
- Depende dos campos e disponibilidade da API do Sporting.
- A verificação corre dentro da hora das 12h (Europe/Lisbon), não necessariamente no minuto exato.
- Ferramenta independente, não oficial do Sporting CP.
