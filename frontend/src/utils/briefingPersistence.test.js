import test from 'node:test';
import assert from 'node:assert/strict';
import { importBrowserFavorites, loadReportFavoriteIds, restoreReportTask } from './briefingPersistence.js';

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

test('刷新从后端恢复当前周期任务，不把其他单篇解读或旧终态认作报告生成', async () => {
  let params;
  const list = async query => { params=query; return {data:[{id:'reading-other',status:'processing',report_context:{kind:'reading',source_id:'source-2'}},{id:'finished',status:'completed',report_context:{kind:'modes'}},{id:'modes-1',status:'processing',report_context:{kind:'modes',mode:'all'}}]}; };
  assert.equal((await restoreReportTask({type:'month',start:'2026-09-01'},'source-1',list)).id,'modes-1');
  assert.deepEqual(params,{type:'briefing-report',period_type:'month',period_start:'2026-09-01',status:'pending,processing',per_page:100});
  assert.equal(await restoreReportTask({type:'week',start:'2026-09-21'},null,async()=>({data:[]})),undefined);
});
