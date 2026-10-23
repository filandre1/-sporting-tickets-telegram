const $ = id => document.getElementById(id);
const state = { games: [], filter: 'all', fetchedAt: '', stale: false };
const weekdays = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado'];
function niceDate(value) {
  const date = new Date(value.slice(0, 10) + 'T12:00:00Z');
  return { day: weekdays[date.getUTCDay()], date: value.slice(8, 10) + '/' + value.slice(5, 7), hour: value.slice(11, 16) };
}
function elt(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}
function render() {
  const target = $('games'); target.replaceChildren();
  const games = state.games.filter(g => state.filter === 'all' || (state.filter === 'football' ? g.football : !g.football));
  for (const g of games) {
    const row = elt('article', 'game'), when = elt('div', 'when'), date = niceDate(g.date);
    when.append(elt('span', 'day', date.day), elt('span', 'date', date.date), elt('span', 'hour', date.hour));
    const main = elt('div', 'game-main'), tags = elt('div', 'tags');
    tags.append(elt('span', 'tag', g.sport),
      elt('span', 'tag ' + (g.soldOut ? 'sold' : ''), g.soldOut ? 'Esgotado' : g.allowSale ? 'À venda' : 'Venda indisponível'));
    if (g.location) tags.append(elt('span', 'tag muted', g.location));
    const title = elt('h3', '', g.home + ' vs ' + g.away);
    const permissions = g.public ? 'Sócios e público' : g.member ? 'Só sócios' : 'Consultar condições';
    const meta = elt('p', 'meta', (g.competition || 'Competição') + ' · ' + permissions);
    main.append(tags, title, meta);
    if (g.token) {
      const a = elt('a', 'ticket-link', 'Abrir bilhetes ↗');
      a.href = 'https://tickets.sporting.pt/' + encodeURIComponent(g.token);
      a.target = '_blank'; a.rel = 'noopener noreferrer'; main.append(a);
    }
    row.append(when, main); target.append(row);
  }
  if (!games.length) target.append(elt('p', 'notice', 'Não existem jogos neste filtro.'));
  const d = state.fetchedAt ? new Date(state.fetchedAt).toLocaleString('pt-PT', { dateStyle:'short',timeStyle:'short',timeZone:'Europe/Lisbon' }) : '';
  $('count').textContent = games.length + ' jogos listados' + (d ? ' · lido às ' + d : '') +
    (state.stale ? ' · dados em cache' : '') + ' · tickets.sporting.pt';
}
async function loadGames(force = false) {
  $('message').textContent = 'A consultar a bilheteira…'; $('refresh').disabled = true;
  try {
    const response = await fetch('/api/games' + (force ? '?force=1' : ''), { cache:'no-store' });
    const data = await response.json();
    if (!response.ok) throw Error(data.error || 'Falha ao carregar jogos');
    state.games = data.games; state.fetchedAt = data.fetchedAt; state.stale = data.stale;
    $('message').textContent = data.stale ? 'A bilheteira não respondeu; a mostrar os últimos dados disponíveis.' : '';
    render();
  } catch (error) { $('message').textContent = error.message; }
  finally { $('refresh').disabled = false; }
}
async function loadStatus() {
  try {
    const res = await fetch('/api/status', { cache:'no-store' }), status = await res.json();
    $('status').textContent = status.configured
      ? 'Alerta configurado. A próxima verificação corre por volta das 12:00.'
      : status.setupReady
        ? 'Ainda não está ligado. Preenche os dados para começar.'
        : 'O servidor precisa de ACCESS_CODE e APP_SECRET para ativar o Telegram.';
    $('status').classList.toggle('ok',status.configured);
  } catch { $('status').textContent = 'Não foi possível verificar a ligação ao Telegram.'; }
}
function feedback(message,error = false) {
  $('form-feedback').textContent = message; $('form-feedback').classList.toggle('error',error);
}
async function post(endpoint,data = {}) {
  const code = $('access').value;
  if (code.length < 8) throw Error('Indica o teu código de acesso (mínimo 8 caracteres).');
  const response = await fetch(endpoint,{method:'POST',headers:{
    'Content-Type':'application/json','X-Access-Code':code
  },body:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw Error(result.error || 'Falha na operação');
  return result;
}
$('telegram-form').addEventListener('submit',async event => {
  event.preventDefault(); $('save').disabled = true; feedback('A guardar configuração…');
  try {
    await post('/api/settings',{
      token:$('token').value.trim(), chatId:$('chat-id').value.trim(),
      footballOnly:$('football-only').checked, notifyWithoutChanges:$('quiet-alert').checked
    });
    $('token').value = '';
    feedback('Configuração guardada. Clica em «Verificar agora» para receber a primeira mensagem.');
    loadStatus();
  } catch(error) { feedback(error.message,true); }
  finally { $('save').disabled = false; }
});
$('check').addEventListener('click',async () => {
  $('check').disabled = true; feedback('A verificar novidades e Telegram…');
  try {
    const result = await post('/api/check');
    feedback(!result.configured ? 'Configura primeiro o bot.'
      : result.busy ? 'Já existe uma verificação em curso.'
      : 'Verificados ' + result.count + ' jogos; ' + result.updates + ' novidades.' +
        (result.notified ? ' Mensagem enviada.' : ' Sem mensagem nova.'));
  } catch(error) { feedback(error.message,true); }
  finally { $('check').disabled = false; }
});
$('refresh').addEventListener('click',()=>loadGames(true));
document.querySelectorAll('[data-filter]').forEach(btn=>btn.addEventListener('click',()=>{
  state.filter = btn.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach(b=>{
    b.classList.toggle('active',b===btn); b.setAttribute('aria-pressed',String(b===btn));
  });
  render();
}));
loadGames(); loadStatus();
