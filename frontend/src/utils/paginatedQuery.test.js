import test from 'node:test';
import assert from 'node:assert/strict';
import { createPaginatedQuery } from './paginatedQuery.js';

const page = (data, current, total, hasNext) => ({ data, pagination: { page: current, per_page: 24, total, has_next: hasNext } });

test('收藏向后端查询全量范围，首屏只取一页并使用服务端总数', async () => {
  const requests = [];
  const query = createPaginatedQuery(async params => {
    requests.push(params);
    return page([{ id: 'old-favorite-501' }], 1, 73, true);
  });
  await query.setParams({ is_starred: true, q: '机器人', sort: 'published_desc' });
  assert.deepEqual(requests, [{ is_starred: true, q: '机器人', sort: 'published_desc', page: 1, per_page: 24 }]);
  assert.equal(query.getState().pagination.total, 73);
  assert.equal(query.getState().data[0].id, 'old-favorite-501');
});

test('加载下一页保留旧条目，连续点击只请求一次，分页结束停止请求', async () => {
  const requests = [];
  let nextPage;
  const query = createPaginatedQuery(params => {
    requests.push(params.page);
    return params.page === 1 ? Promise.resolve(page([{ id: 'a' }], 1, 2, true)) : new Promise(resolve => { nextPage = resolve; });
  });
  await query.setParams({});
  const next = query.loadMore();
  const duplicate = query.loadMore();
  assert.equal(next, duplicate);
  nextPage(page([{ id: 'b' }], 2, 2, false));
  await next;
  assert.deepEqual(query.getState().data.map(item => item.id), ['a', 'b']);
  await query.loadMore();
  assert.deepEqual(requests, [1, 2]);
});

test('快速切换订阅时旧响应不覆盖新列表，搜索重新从第一页开始', async () => {
  let finishOld;
  const query = createPaginatedQuery(params => params.feed_id === 'old'
    ? new Promise(resolve => { finishOld = resolve; })
    : Promise.resolve(page([{ id: 'new-item' }], 1, 1, false)));
  const old = query.setParams({ feed_id: 'old' });
  await query.setParams({ feed_id: 'new', q: '新主题' });
  finishOld(page([{ id: 'old-item' }], 1, 1, false));
  await old;
  assert.deepEqual(query.getState().data.map(item => item.id), ['new-item']);
});

test('加载失败保留已显示列表并允许重试，离开页面不再通知', async () => {
  let attempts = 0;
  const updates = [];
  const query = createPaginatedQuery(async params => {
    attempts += 1;
    if (attempts === 2) throw { message: '暂时无法加载' };
    return page([{ id: String(params.page) }], params.page, 2, params.page === 1);
  }, state => updates.push(state));
  await query.setParams({ processed: true, has_transcript: true });
  await query.loadMore();
  assert.equal(query.getState().error, '暂时无法加载');
  assert.equal(query.getState().data[0].id, '1');
  await query.loadMore();
  assert.equal(query.getState().data.length, 2);
  query.dispose();
  const count = updates.length;
  await query.reload();
  assert.equal(updates.length, count);
});

test('只对当前成功加载的列表记录查看，旧响应和离开页面后的响应不记为看过', async () => {
  const pending = new Map();
  const viewed = [];
  const query = createPaginatedQuery(params => new Promise(resolve => pending.set(params.feed_id, resolve)),
    () => {}, 24, response => viewed.push(response.meta.latest_episode_id));
  const old = query.setParams({ feed_id: 'old' });
  const current = query.setParams({ feed_id: 'current' });
  pending.get('current')({ ...page([{ id: 'current-episode' }], 1, 1, false), meta: { latest_episode_id: 'current-snapshot' } });
  await current;
  pending.get('old')({ ...page([{ id: 'old-episode' }], 1, 1, false), meta: { latest_episode_id: 'old-snapshot' } });
  await old;
  const leaving = query.setParams({ feed_id: 'leaving' });
  query.dispose();
  pending.get('leaving')({ ...page([], 1, 0, false), meta: { latest_episode_id: 'leaving-snapshot' } });
  await leaving;
  assert.deepEqual(viewed, ['current-snapshot']);
});

test('列表加载失败不会清除未查看的更新', async () => {
  let viewed = false;
  const query = createPaginatedQuery(async () => { throw new Error('加载失败'); },
    () => {}, 24, () => { viewed = true; });
  await query.setParams({});
  assert.equal(viewed, false);
  assert.equal(query.getState().error, '加载失败');
});
