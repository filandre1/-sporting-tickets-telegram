# Deploy no Render — Alerta Bilhetes Sporting

Este projeto usa um Web Service Node.js com HTTPS e **disco persistente**. O ficheiro `render.yaml`, na raiz do repositório, contém a configuração. O monitor Python e os seus GitHub Actions não são alterados.

## 1. Criar o serviço

1. Entra em **https://dashboard.render.com/**.
2. Liga a tua conta GitHub, se ainda não estiver ligada.
3. Abre **New → Blueprint** e escolhe `filandre1/-sporting-tickets-telegram`.
4. Seleciona a branch `main` e o ficheiro `render.yaml`.
5. Confirma a configuração antes de clicar em **Deploy Blueprint**:
   - Web Service Node na região `frankfurt`.
   - Plano pago `0.5c-512mb` (anteriormente chamado Starter), um único processo.
   - Diretório `web/`, arranque `npm start`, testes de build com `npm test`.
   - Disco `sporting-alerta-data` de 1 GB montado em `/var/data`.
   - `DATA_DIR=/var/data`.
   - `APP_SECRET` gerado automaticamente e mantido privado.
6. Quando solicitado, escolhe **ACCESS_CODE**: uma palavra-passe longa e única. Nunca a publiques no GitHub nem a partilhes. Exemplo de formato (não copiar literalmente): `palavras-aleatorias-com-mais-de-20-caracteres`.
7. Confirma a criação do serviço e os preços apresentados antes de aceitares a cobrança.

**Importante:** o Render precisa de uma conta e da aprovação do utilizador para criar um serviço pago. O ficheiro no repositório não cria alojamento por si só.

## 2. Validar o primeiro deploy

O Render atribui automaticamente um endereço `https://<nome-real>.onrender.com` e gere o certificado TLS.

- Abre o endereço HTTPS indicado no Dashboard.
- Visita `/api/health` no **teu endereço real**: deve devolver `{"ok":true}`.
- A interface deve abrir mesmo que a bilheteira oficial esteja temporariamente indisponível. Confirma os filtros Todos/Futebol/Modalidades.
- No painel Telegram, usa o token do bot, ID do chat e `ACCESS_CODE` definido no Render. Clica em **Guardar alerta** e depois em **Verificar agora**.
- Confirma se recebeste uma mensagem no Telegram, caso existam jogos novos ou listados na primeira verificação.

O endpoint de saúde confirma que as variáveis de segurança estão definidas e que o processo tem acesso de leitura/escrita ao diretório configurado. **Não certifica**, por si só, que o disco foi corretamente anexado; confirma também o disco no painel Render, em **Disks**.

## 3. Segurança e persistência

- O Render termina HTTPS na sua infraestrutura, por isso o processo Node serve HTTP internamente.
- Guarda **ACCESS_CODE** e **APP_SECRET** como variáveis privadas do Render; nunca no GitHub.
- O token e o chat ID do Telegram são cifrados com AES-256-GCM antes de serem gravados em `/var/data/settings.enc.json`. O histórico fica em `/var/data/state.json`.
- Mantém a **mesma** `APP_SECRET` em deploys futuros. Se mudares a chave, deixas de conseguir ler a configuração anterior.
- Testa a persistência: guarda a configuração, reinicia o serviço pelo Render, e confirma que o painel continua a mostrar "Alerta configurado".
- Não apagues o disco sem exportar os dados importantes. Consulta a funcionalidade de snapshots do Render para recuperação.
- Apenas uma instância deve executar o agendador, evitando duplicação de mensagens e concorrência na escrita dos ficheiros.

## 4. Evitar duplicação de alertas

O GitHub Actions original continua a executar `monitor.py`, que pode já enviar notificações. Se ligares a aplicação web ao **mesmo chat**, poderás receber avisos duplicados. Para migrar, confirma primeiro que a versão web funciona e, depois, desativa o agendamento do workflow Python (mantendo a possibilidade de execução manual), ou usa chats diferentes.

## 5. Operação

- O serviço fica ativo e verifica os jogos durante a hora das **12:00 de Lisboa**, incluindo mudanças entre hora de verão/inverno.
- Novas alterações na branch `main` desencadeiam um novo deploy; o disco continua associado.
- O disco dedicado impede deploys sem interrupção (pode haver alguns segundos de indisponibilidade).
- A aplicação depende da disponibilidade e do formato da API da bilheteira oficial.
- O serviço Render **gratuito não é adequado**: sem disco persistente e sujeito a suspensão por inatividade.

## Custos

O plano `0.5c-512mb` custa aproximadamente **7 USD/mês**, com **0,25 USD/mês** por 1 GB de SSD, segundo a tabela publicada. Impostos e consumos adicionais podem aplicar-se. Confirma sempre o valor no ecrã de criação antes de ativar a faturação.

### Documentação

- https://render.com/docs/infrastructure-as-code
- https://render.com/docs/blueprint-spec
- https://render.com/docs/disks
- https://render.com/docs/health-checks
- https://render.com/docs/tls
- https://render.com/pricing
