import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomBytes, createCipheriv, createDecipheriv, scryptSync, timingSafeEqual } from 'node:crypto';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC = path.join(ROOT, 'public');
const DATA = path.resolve(process.env.DATA_DIR || path.join(ROOT, 'data'));
const HOST = process.env.HOST || '0.0.0.0';
const PORT = Number(process.env.PORT || 3000);
const TICKETS_API = 'https://tickets.sporting.pt/api/match/allopengames';
const CACHE_MS = 5 * 60 * 1000;
let cache = { at: 0, games: [] };
let checking = false, lastScheduledDay = null;
const failedAuth = new Map();

const lisbonDay = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Lisbon', year: 'numeric', month: '2-digit', day: '2-digit' });
const lisbonHour = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Lisbon', hour: '2-digit', hourCycle: 'h23' });
function localDay(d = new Date()) {
  const p = Object.fromEntries(lisbonDay.formatToParts(d).filter(p => p.type !== 'literal').map(p => [p.type, p.value]));
  return [p.year, p.month, p.day].join('-');
}
function isFootball(g) { return Number(g.modalityId) === 1 || /futebol/i.test(String(g.modality || '')); }
function text(v) { return String(v ?? '').trim().slice(0, 200); }
function normalizeGames(raw) {
  if (!Array.isArray(raw)) throw Error('Formato de bilheteira inválido');
  return raw.map(g => {
    const home = text(g.homeTeam?.name), away = text(g.awayTeam?.name);
    const date = String(g.date || '');
    return {
      id: String(g.id ?? g.token ?? ''),
      token: /^[A-Za-z0-9_-]+$/.test(String(g.token || '')) ? String(g.token) : '',
      date: /^\d{4}-\d\d-\d\dT\d\d:\d\d/.test(date) ? date.slice(0, 19) : '',
      sport: text(g.modality || (isFootball(g) ? 'Futebol' : 'Modalidade')),
      football: isFootball(g), competition: text(g.competition), home, away,
      soldOut: Boolean(g.soldOut), allowSale: Boolean(g.allowSale),
      public: Boolean(g.public), member: Boolean(g.member),
      location: /sporting/i.test(home) ? 'Casa' : /sporting/i.test(away) ? 'Fora' : ''
    };
  }).filter(g => g.id && g.date && g.home && g.away).sort((a, b) => a.date.localeCompare(b.date));
}
async function fetchGames(force = false) {
  if (!force && cache.at && Date.now() - cache.at < CACHE_MS) return cache.games;
  const r = await fetch(TICKETS_API, { headers: {
    'User-Agent': 'Mozilla/5.0 (compatible; SportingTicketAlert/1.0)',
    'Accept': 'application/json', 'Referer': 'https://tickets.sporting.pt/'
  }, signal: AbortSignal.timeout(15000) });
  if (!r.ok) throw Error('Bilheteira indisponível');
  const games = normalizeGames((await r.json())?.data?.openGames);
  cache = { at: Date.now(), games };
  return games;
}
async function loadJson(filename, fallback) {
  try { return JSON.parse(await fs.readFile(path.join(DATA, filename), 'utf8')); }
  catch (e) { if (e.code === 'ENOENT') return fallback; throw e; }
}
async function saveJson(filename, obj) {
  await fs.mkdir(DATA, { recursive: true, mode: 0o700 });
  const tmp = path.join(DATA, '.' + filename + '.' + process.pid + '.tmp');
  await fs.writeFile(tmp, JSON.stringify(obj, null, 2), { mode: 0o600 });
  await fs.rename(tmp, path.join(DATA, filename));
}
function key() {
  if (!process.env.APP_SECRET || process.env.APP_SECRET.length < 32) throw Error('APP_SECRET em falta');
  return scryptSync(process.env.APP_SECRET, 'sporting-alerta-v1', 32);
}
function encrypt(obj) {
  const iv = randomBytes(12), cipher = createCipheriv('aes-256-gcm', key(), iv);
  const ciphertext = Buffer.concat([cipher.update(JSON.stringify(obj)), cipher.final()]);
  return { iv: iv.toString('base64'), ciphertext: ciphertext.toString('base64'), tag: cipher.getAuthTag().toString('base64') };
}
function decrypt(obj) {
  const d = createDecipheriv('aes-256-gcm', key(), Buffer.from(obj.iv, 'base64'));
  d.setAuthTag(Buffer.from(obj.tag, 'base64'));
  return JSON.parse(Buffer.concat([d.update(Buffer.from(obj.ciphertext, 'base64')), d.final()]).toString('utf8'));
}
async function settings() { const saved = await loadJson('settings.enc.json', null); return saved ? decrypt(saved) : null; }
function authorized(req) {
  const expected = process.env.ACCESS_CODE || '';
  if (expected.length < 8) return false;
  const a = Buffer.from(String(req.headers['x-access-code'] || '')), b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}
function json(res, status, value) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer' });
  res.end(JSON.stringify(value));
}
async function readBody(req) {
  const chunks = []; let total = 0;
  for await (const part of req) {
    total += part.length;
    if (total > 8192) { const e = Error('Pedido demasiado grande'); e.status = 413; throw e; }
    chunks.push(part);
  }
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')); }
  catch { const e = Error('JSON inválido'); e.status = 400; throw e; }
}
function fingerprint(g) {
  return JSON.stringify([g.date,g.sport,g.competition,g.home,g.away,g.soldOut,g.allowSale,g.public,g.member,g.token]);
}
function formatGame(g) {
  const date = g.date.slice(8,10) + '/' + g.date.slice(5,7) + ' ' + g.date.slice(11,16);
  const access = g.public ? 'Sócios e público' : g.member ? 'Sócios' : 'Consultar condições';
  return date + ' · ' + g.sport + '\n' + g.home + ' vs ' + g.away + '\n' +
    g.competition + ' · ' + (g.soldOut ? 'Esgotado' : access) +
    '\nhttps://tickets.sporting.pt/' + g.token;
}
async function sendTelegram(config, message) {
  const chunks = []; let block = '';
  for (const line of message.split('\n')) {
    if (block.length + line.length + 1 > 3900) { chunks.push(block); block = ''; }
    block += (block ? '\n' : '') + line;
  }
  if (block) chunks.push(block);
  for (const msg of chunks) {
    const response = await fetch('https://api.telegram.org/bot' + config.token + '/sendMessage', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: config.chatId, text: msg, disable_web_page_preview: true }),
      signal: AbortSignal.timeout(12000)
    });
    if (!response.ok) throw Error('Telegram recusou a mensagem. Confirma o token e o chat.');
  }
}
async function checkAlerts(scheduled = false) {
  if (checking) return { busy: true };
  checking = true;
  try {
    const config = await settings();
    if (!config) return { configured: false };
    const games = (await fetchGames(true)).filter(g => !config.footballOnly || g.football);
    const state = await loadJson('state.json', { previous: null, lastDaily: null });
    const current = Object.fromEntries(games.map(g => [g.id, fingerprint(g)]));
    const updates = state.previous === null ? games : games.filter(g => state.previous[g.id] !== current[g.id]);
    const day = localDay();
    const dailyQuiet = scheduled && config.notifyWithoutChanges && state.lastDaily !== day;
    let notified = false;
    if (updates.length || dailyQuiet) {
      const heading = state.previous === null ? '🟢 Jogos atualmente disponíveis' :
        updates.length ? '🚨 Novidades na bilheteira do Sporting CP' : 'ℹ️ Sem novidades na bilheteira do Sporting CP.';
      await sendTelegram(config, heading + (updates.length ? '\n\n' + updates.map(formatGame).join('\n\n') : ''));
      notified = true;
    }
    await saveJson('state.json', { previous: current, lastDaily: scheduled ? day : state.lastDaily });
    return { configured: true, count: games.length, updates: updates.length, notified };
  } finally { checking = false; }
}
async function scheduler() {
  if (Number(lisbonHour.format(new Date())) !== 12 || lastScheduledDay === localDay()) return;
  try {
    if (!(await settings())) return;
    const result = await checkAlerts(true);
    if (!result.busy) lastScheduledDay = localDay();
  } catch (e) { console.error('Falha na verificação diária:', e.message); }
}
const FILES = { '/': ['index.html','text/html'], '/index.html': ['index.html','text/html'],
  '/styles.css': ['styles.css','text/css'], '/app.js': ['app.js','text/javascript'] };
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost'), route = url.pathname;
  res.setHeader('X-Frame-Options','DENY');
  res.setHeader('Content-Security-Policy', "default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'");
  try {
    if (req.method === 'GET' && FILES[route]) {
      const [file,type] = FILES[route];
      res.writeHead(200,{ 'Content-Type':type+'; charset=utf-8', 'Cache-Control':'no-cache' });
      return res.end(await fs.readFile(path.join(PUBLIC,file)));
    }
    if (req.method === 'GET' && route === '/api/games') {
      try { return json(res,200,{ games:await fetchGames(url.searchParams.has('force')),fetchedAt:new Date(cache.at).toISOString(),stale:false }); }
      catch { return cache.at ? json(res,200,{ games:cache.games,fetchedAt:new Date(cache.at).toISOString(),stale:true }) :
        json(res,503,{ error:'Não foi possível contactar a bilheteira neste momento.' }); }
    }
    if (req.method === 'GET' && route === '/api/status') {
      return json(res,200,{ configured:Boolean(await settings()),
        setupReady:Boolean(process.env.ACCESS_CODE?.length >= 8 && process.env.APP_SECRET?.length >= 32) });
    }
    if (route === '/api/settings' || route === '/api/check') {
      if (req.method !== 'POST') return json(res,405,{ error:'Método não permitido' });
      const ip = req.socket.remoteAddress || 'unknown';
      const attempt = failedAuth.get(ip) || { n:0,until:0 };
      if (Date.now() < attempt.until) return json(res,429,{error:'Demasiadas tentativas. Experimenta mais tarde.'});
      if (!authorized(req)) {
        const n = attempt.n + 1;
        failedAuth.set(ip,{n,until:n >= 8 ? Date.now()+15*60*1000 : 0});
        return json(res,401,{error:'Código de acesso inválido.'});
      }
      failedAuth.delete(ip);
      if (route === '/api/check') return json(res,200,await checkAlerts());
      const body = await readBody(req);
      const token = String(body.token || '').trim(), chatId = String(body.chatId || '').trim();
      if (!/^\d{5,15}:[A-Za-z0-9_-]{20,}$/.test(token)) return json(res,400,{error:'Token do bot inválido.'});
      if (!/^-?\d{4,25}$/.test(chatId)) return json(res,400,{error:'ID do chat inválido.'});
      await saveJson('settings.enc.json',encrypt({token,chatId,footballOnly:Boolean(body.footballOnly),notifyWithoutChanges:Boolean(body.notifyWithoutChanges)}));
      await saveJson('state.json',{previous:null,lastDaily:null});
      return json(res,200,{ok:true});
    }
    json(res,404,{error:'Página não encontrada'});
  } catch(e) {
    console.error('Erro na aplicação:',e.message);
    json(res,e.status || 500,{error:e.status ? e.message : 'Não foi possível concluir a operação.'});
  }
});
server.listen(PORT,HOST,()=>console.log('Alerta Bilhetes Sporting disponível na porta '+PORT));
setInterval(scheduler,60000).unref();
scheduler();
