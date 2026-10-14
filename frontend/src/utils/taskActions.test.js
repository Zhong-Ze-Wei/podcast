import test from 'node:test';
import assert from 'node:assert/strict';
import { createFeedRefreshAction, canCancelTask, isTerminalTask, createTerminalNotifier, requestTaskCancellation } from './taskActions.js';

test('同一订阅的刷新只提交一个后端任务，提交成功后通知 task ID', async () => {
  const calls = [];
  let resolveRefresh;
  const action = createFeedRefreshAction({
    refresh: id => { calls.push(id); return new Promise(resolve => { resolveRefresh = resolve; }); },
    onQueued: task => calls.push(task.task_id),
  });
  const first = action('feed-1');
  const duplicate = action('feed-1');
  assert.equal(first, duplicate);
  await Promise.resolve();
  resolveRefresh({ data: { task_id: 'refresh-1', status: 'queued' } });
  assert.deepEqual(await first, { task_id: 'refresh-1', status: 'queued' });
  assert.deepEqual(calls, ['feed-1', 'refresh-1']);
});

test('刷新失败展示后端原因并允许重试，不触发成功回调', async () => {
  let attempts = 0;
  const errors = [];
  const queued = [];
  const action = createFeedRefreshAction({
    refresh: async () => { attempts += 1; if (attempts === 1) throw { message: '源站暂不可用' }; return { data: { task_id: 'refresh-2' } }; },
    onError: error => errors.push(error.message),
    onQueued: task => queued.push(task.task_id),
  });
  await action('feed-1');
  assert.deepEqual(errors, ['源站暂不可用']);
  assert.deepEqual(queued, []);
  await action('feed-1');
  assert.deepEqual(queued, ['refresh-2']);
});

test('只有后端明确支持取消且未请求取消的活动任务显示取消操作', () => {
  assert.equal(canCancelTask({ status: 'pending', can_cancel: true }), true);
  assert.equal(canCancelTask({ status: 'processing', can_cancel: true }), true);
  assert.equal(canCancelTask({ status: 'pending', can_cancel: false }), false);
  assert.equal(canCancelTask({ status: 'processing', can_cancel: true, cancel_requested: true }), false);
  assert.equal(canCancelTask({ status: 'cancelled', can_cancel: true }), false);
});

test('取消是独立终态，每个任务仅发出一次终态通知', () => {
  assert.equal(isTerminalTask({ status: 'cancelled' }), true);
  assert.equal(isTerminalTask({ status: 'processing', cancel_requested: true }), false);
  const notifications = [];
  const notify = createTerminalNotifier(task => notifications.push(task.status));
  notify({ id: 't1', status: 'processing' });
  notify({ id: 't1', status: 'cancelled' });
  notify({ id: 't1', status: 'cancelled' });
  notify({ id: 't2', status: 'completed' });
  assert.deepEqual(notifications, ['cancelled', 'completed']);
});

test('取消失败保留真实任务状态并展示后端原因，成功后重新读取状态', async () => {
  const events = [];
  await requestTaskCancellation('t1', {
    cancel: async () => { throw { message: '运行中的任务当前无法停止' }; },
    refresh: async () => events.push('refresh'),
    onError: error => events.push(error.message),
  });
  assert.deepEqual(events, ['运行中的任务当前无法停止']);
  await requestTaskCancellation('t1', {
    cancel: async id => events.push(id),
    refresh: async () => events.push('refresh'),
    onError: error => events.push(error.message),
  });
  assert.deepEqual(events, ['运行中的任务当前无法停止', 't1', 'refresh']);
});
