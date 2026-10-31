const $ = id => document.getElementById(id);
const state = { games: [], filter: 'all', fetchedAt: null, generatedAt: null, stale: false, source: '', scope: '' };
const weekdays = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado'];

function niceDate(value) {
  const date = new Date(value.slice(0, 10) + 'T12:00:00Z');
  return {
    day: weekdays[date.getUTCDay()],
    date: value.slice(8, 10) + '/' + value.slice(5, 7),
    hour: value.slice(11, 16)
  };
}
function elt(tag, cls = '', value) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (value !== undefined) e.textContent = String(value);
  return e;
}
function formatTimestamp(s) {
  if (!s || Number.isNaN(Date.parse(s))) return 'hora desconhecida';
  return new Date(s).toLocaleString('pt-PT', {
    dateStyle: 'short', timeStyle: 'short', timeZone: 'Europe/Lisbon'
  });
}
function render() {
  const target = $('games');
  target.replaceChildren();
  const games = state.games.filter(g =>
    state.filter === 'all' || (state.filter === 'football' ? g.football : !g.football)
  );
  for (const g of games) {
    const row = elt('article', 'game');
    const when = elt('div', 'when');
    const date = niceDate(g.date);
    when.append(elt('span', 'day', date.day),
      elt('span', 'date', date.date),
      elt('span', 'hour', date.hour));

    const main = elt('div', 'game-main');
    const tags = elt('div', 'tags');
    tags.append(
      elt('span', 'tag', g.sport),
      elt('span', 'tag ' + (g.soldOut ? 'sold' : ''),
        g.soldOut ? 'Esgotado' : g.disabledReasonDesc ? g.disabledReasonDesc : g.allowSale === false ? 'Venda indisponível' : g.allowSale === true ? 'Venda permitida (confirmar)' : 'Estado não indicado')
    );
    if (g.location) tags.append(elt('span', 'tag muted', g.location));
    const heading = elt('h3', '', g.event || ((g.home || '') + ' vs ' + (g.away || '')));
    const permission = g.public === true ? 'Acesso a público indicado' : g.member === true ? 'Acesso a sócios indicado' : 'Consultar condições';
    const meta = elt('p', 'meta', (g.competition || 'Competição') + ' · ' + permission);
    main.append(tags, heading, meta);
    if (/^[A-Za-z0-9_-]+$/.test(String(g.token || ''))) {
      const link = elt('a', 'ticket-link', 'Consultar bilhetes ↗');
      link.href = 'https://tickets.sporting.pt/' + encodeURIComponent(g.token);
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      main.append(link);
    }
    row.append(when, main);
    target.append(row);
  }
  if (!games.length) {
    target.append(elt('p', 'notice',
      state.stale && state.scope === 'football_only' && state.filter === 'other'
        ? 'Sem dados atuais sobre outras modalidades. A próxima recolha tentará atualizar a lista.'
        : 'Não existem jogos disponíveis neste filtro, segundo a última publicação.'
    ));
  }
  $('count').textContent = games.length + ' jogos · Última consulta: ' +
    formatTimestamp(state.fetchedAt) +
    (state.stale ? ' · dados desatualizados (' + (state.scope === 'football_only' ? 'só futebol' : 'todas as modalidades') + ')' : ' · Fonte: bilheteira oficial');
}
async function loadGames() {
  const button = $('refresh');
  button.disabled = true;
  $('message').textContent = 'A ler os dados publicados…';
  try {
    // Recarrega o JSON que o GitHub Actions gerou; não é uma consulta em tempo real.
    const response = await fetch('./games.json?v=' + Date.now(), { cache: 'no-store' });
    if (!response.ok) throw Error('Não foi possível carregar o ficheiro de jogos.');
    const data = await response.json();
    if (!Array.isArray(data.games)) throw Error('Os dados de jogos não são válidos.');
    Object.assign(state, {
      games: data.games, fetchedAt: data.fetchedAt,
      generatedAt: data.generatedAt, stale: Boolean(data.stale), source: data.source, scope: data.scope
    });
    $('message').textContent = state.stale
      ? 'Atenção: a última consulta falhou. Informação desatualizada (' + (state.scope === 'football_only' ? 'apenas futebol' : 'futebol e modalidades') + ').'
      : 'Última publicação do GitHub Actions: ' + formatTimestamp(state.generatedAt) +
        '. Recarregar não força nova consulta à bilheteira.';
    render();
  } catch (error) {
    $('message').textContent = error.message;
    $('count').textContent = 'Tenta novamente mais tarde ou consulta a bilheteira oficial.';
  } finally {
    button.disabled = false;
  }
}
$('refresh').addEventListener('click', loadGames);
document.querySelectorAll('[data-filter]').forEach(btn =>
  btn.addEventListener('click', () => {
    state.filter = btn.dataset.filter;
    document.querySelectorAll('[data-filter]').forEach(b => {
      b.classList.toggle('active', b === btn);
      b.setAttribute('aria-pressed', String(b === btn));
    });
    render();
  })
);
loadGames();
