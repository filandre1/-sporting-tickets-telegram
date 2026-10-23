import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import net from 'node:net';
import { spawn } from 'node:child_process';

async function freePort() {
  const server = net.createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return port;
}

test('HTTP, autenticação e armazenamento cifrado', async () => {
  const port = await freePort();
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'sporting-web-test-'));
  const access = 'codigo-de-teste-2026';
  const secret = 'uma-chave-de-teste-muito-longa-com-mais-de-trinta-e-dois';
  const child = spawn(process.execPath, ['server.mjs'], {
    cwd: path.resolve(import.meta.dirname, '..'),
    env: { ...process.env, PORT: String(port), HOST: '127.0.0.1', DATA_DIR: dir, ACCESS_CODE: access, APP_SECRET: secret },
    stdio: 'ignore'
  });
  const base = 'http://127.0.0.1:' + port;
  try {
    let ready = false;
    for (let i = 0; i < 60; i++) {
      try { const r = await fetch(base + '/api/status'); ready = r.status === 200; if (ready) break; }
      catch { await new Promise(resolve => setTimeout(resolve, 50)); }
    }
    assert.ok(ready, 'Servidor arrancou');
    const health = await fetch(base + '/api/health');
    assert.equal(health.status, 200, 'Health check responde com HTTP 200');
    assert.deepEqual(await health.json(), { ok: true });

    const root = await fetch(base);
    assert.equal(root.status, 200);
    assert.match(await root.text(), /ALERTA/);
    const authFail = await fetch(base + '/api/check', { method: 'POST' });
    assert.equal(authFail.status, 401);
    const token = '123456789:AAabcdefghijklmnopqrstuvwxyz';
    const saved = await fetch(base + '/api/settings', { method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Access-Code': access },
      body: JSON.stringify({ token, chatId: '12345678', footballOnly: true }) });
    assert.equal(saved.status, 200);
    const encrypted = await fs.readFile(path.join(dir, 'settings.enc.json'), 'utf8');
    assert.ok(!encrypted.includes(token), 'Token cifrado, não guardado em texto simples');
    const status = await (await fetch(base + '/api/status')).json();
    assert.equal(status.configured, true);
  } finally {
    child.kill('SIGTERM');
    await fs.rm(dir, { recursive: true, force: true });
  }
});
