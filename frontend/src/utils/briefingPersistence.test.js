import test from 'node:test';
import assert from 'node:assert/strict';
import { importBrowserFavorites, loadReportFavoriteIds } from './briefingPersistence.js';

function storage(initial) { let value = JSON.stringify(initial); return { getItem: () => value, setItem: (_key, next) => { value = next; }, read: () => JSON.parse(value) }; }

test('旧收藏只移除后端确认导入的ID，无法匹配的ID保留且可重试', async () => {
  const local = storage(['saved', 'missing']);
  const calls = [];
  const result = await importBrowserFavorites(local, 'user-a:quotes', async ids => { calls.push(ids); return { data: { imported: ['saved'], unresolved: ['missing'] } }; });
  assert.deepEqual(calls, [['saved', 'missing']]);
  assert.deepEqual(result.unresolved, ['missing']);
  assert.deepEqual(local.read(), ['missing']);
});

test('导入失败保留全部本地IDs，大量收藏按后端500项上限分批', async () => {
  const local = storage(['saved', 'missing']);
  await assert.rejects(importBrowserFavorites(local, 'user-a:quotes', async () => { throw new Error('连接失败'); }));
  assert.deepEqual(local.read(), ['saved', 'missing']);
  const many = storage(Array.from({ length: 501 }, (_, i) => `id-${i}`));
  const sizes = [];
  await importBrowserFavorites(many, 'user-a:quotes', async ids => { sizes.push(ids.length); return { data: { imported: ids, unresolved: [] } }; });
  assert.deepEqual(sizes, [500, 1]);
  assert.deepEqual(many.read(), []);
});

test('阅读页从后端按报告周期和模式查收藏标记，包括第二页保存的条目', async () => {
  const requests = [];
  const ids = await loadReportFavoriteIds({ period: { type: 'week', start: '2026-09-21' }, mode: 'quotes' }, async params => {
    requests.push(params);
    return { data: [{ item_id: `saved-${params.page}` }], pagination: { page: params.page, has_next: params.page === 1 } };
  });
  assert.deepEqual(ids, ['saved-1', 'saved-2']);
  assert.equal(requests.length, 2);
  assert.equal(requests[0].period_type, 'week');
  assert.equal(requests[0].period_start, '2026-09-21');
  assert.equal(requests[0].mode, 'quotes');
});
