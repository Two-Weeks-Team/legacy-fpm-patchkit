import test from 'node:test';
import assert from 'node:assert/strict';
import { collectGithub, API_URL } from '../src/github.ts';
import { raw } from './fixtures.ts';

const page = (rows: unknown[], link?: string) => new Response(JSON.stringify(rows), {
  headers: { 'Content-Type': 'application/json', ...(link ? { Link: link } : {}) },
});

test('follows all official next-page links and returns complete sorted identities', async () => {
  const urls: string[] = [];
  const result = await collectGithub(async (url, init) => {
    urls.push(url); assert.equal(init.redirect, 'manual');
    return urls.length === 1 ? page([raw()], `<${API_URL}&after=cursor>; rel="next"`) : page([raw('GHSA-dddd-eeee-ffff')]);
  });
  assert.equal(result.length, 2); assert.equal(urls.length, 2);
});

test('later-page failure rejects the complete batch rather than returning a partial catalog', async () => {
  let calls = 0;
  await assert.rejects(collectGithub(async () => ++calls === 1 ? page([raw()], `<${API_URL}&after=x>; rel="next"`) : new Response('rate limited', { status: 403 })), /403/);
});

test('foreign pagination destinations are rejected before any fetch or credential forwarding', async () => {
  let calls = 0;
  await assert.rejects(collectGithub(async () => { calls++; return page([raw()], '<https://evil.example/api>; rel="next"'); }), /pagination/);
  assert.equal(calls, 1);
});

test('pagination cycles and duplicated identities cannot pass as a complete catalog', async () => {
  await assert.rejects(collectGithub(async () => page([raw()], `<${API_URL}>; rel="next"`)), /cycle/);
  let calls = 0;
  await assert.rejects(collectGithub(async () => ++calls === 1 ? page([raw()], `<${API_URL}&after=x>; rel="next"`) : page([raw()])), /Duplicate/);
});

test('oversized and empty responses fail without replacing a previous snapshot', async () => {
  await assert.rejects(collectGithub(async () => page([raw()]), { maxPageBytes: 20 }), /budget/);
  await assert.rejects(collectGithub(async () => page([])), /empty/);
});

test('a trickling response cannot extend the absolute collection deadline', async () => {
  const body = new ReadableStream<Uint8Array>({
    async pull(controller) { await new Promise(resolve => setTimeout(resolve, 15)); controller.enqueue(new TextEncoder().encode(' ')); },
  });
  await assert.rejects(collectGithub(async () => new Response(body), { timeoutMs: 40 }), /deadline/);
});

test('non-JSON and malformed advisory data are rejected', async () => {
  await assert.rejects(collectGithub(async () => new Response('not json')), /JSON/);
  await assert.rejects(collectGithub(async () => page([{ ...raw(), ghsa_id: 'bad' }])), /GHSA/);
});
