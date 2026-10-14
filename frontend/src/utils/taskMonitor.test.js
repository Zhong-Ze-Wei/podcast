import test from 'node:test';
import assert from 'node:assert/strict';
import { createTaskMonitor, submitTranscription, getEpisodeTaskId } from './taskMonitor.js';

test('本地转写只提交一次编排请求，必要下载交给后端，保留明确任务ID', async () => {
  const calls = [];
  const task = await submitTranscription('episode-1', 'local_whisper', 'zh', async (id, options) => {
    calls.push({ id, options });
    return { data: { task_id: 'transcribe-1', status: 'queued' } };
  });
  assert.deepEqual(calls, [{ id: 'episode-1', options: { provider: 'local_whisper', language: 'zh', download_if_needed: true } }]);
  assert.equal(task.task_id, 'transcribe-1');
  assert.equal(getEpisodeTaskId({ active_tasks: [{ task_type: 'transcribe', task_id: 'persisted-1' }] }, 'transcribe'), 'persisted-1');
  assert.equal(getEpisodeTaskId({ active_tasks: [] }, 'transcribe', 'submitted-1'), 'submitted-1');
});

test('任务中心和详情共享刷新，首次历史不触发刷新，新终态仅通知一次', async () => {
  let complete = false;
  let requests = 0;
  const terminal = [];
  const monitor = createTaskMonitor({
    list: async params => { requests += 1; return { data: params.status.includes('pending') ? (complete ? [] : [{ id: 'new', status: 'processing' }]) : [{ id: 'old', status: 'completed' }, ...(complete ? [{ id: 'new', status: 'cancelled' }] : [])] }; },
    get: async () => { throw new Error('列表里已有任务，不应额外请求'); },
    onTerminal: tasks => terminal.push(...tasks.map(task => task.id)),
  });
  const first = monitor.refresh();
  assert.equal(first, monitor.refresh());
  await first;
  assert.deepEqual(terminal, []);
  monitor.watch('new');
  complete = true;
  await monitor.refresh();
  await monitor.refresh();
  assert.deepEqual(terminal, ['new']);
  assert.equal(requests, 6);
});

test('刷新页面后按明确ID恢复未出现在任务列表中的任务，不误认旧任务', async () => {
  const requested = [];
  const monitor = createTaskMonitor({
    list: async () => ({ data: [] }),
    get: async id => { requested.push(id); return { data: { id, status: 'processing', type: 'transcribe' } }; },
  });
  monitor.watch('explicit-task');
  await monitor.refresh();
  assert.deepEqual(requested, ['explicit-task']);
  assert.equal(monitor.getState().byId['explicit-task'].status, 'processing');
});

test('后端取消拒绝保留processing，展示原因；卸载后迟到响应不发业务通知', async () => {
  const changes = [];
  const monitor = createTaskMonitor({
    list: async () => ({ data: [{ id: 'running', status: 'processing' }] }),
    get: async () => ({ data: null }),
    cancel: async () => { throw { message: '该任务目前无法停止' }; },
    onChange: state => changes.push(state),
  });
  await monitor.refresh();
  await monitor.cancel('running');
  assert.equal(monitor.getState().byId.running.status, 'processing');
  assert.equal(monitor.getState().error, '该任务目前无法停止');
  monitor.dispose();
  const count = changes.length;
  await monitor.refresh();
  assert.equal(changes.length, count);
});

test('活跃队列超过一页时仍全部可见，不因首屏请求上限遗漏任务', async () => {
  const pages = [];
  const monitor = createTaskMonitor({
    list: async params => {
      if (!params.status.includes('pending')) return { data: [] };
      const page = params.page || 1;
      pages.push(page);
      return { data: Array.from({ length: page === 1 ? 100 : 1 }, (_, i) => ({ id: `task-${page}-${i}`, status: 'pending' })), pagination: { page, has_next: page === 1 } };
    },
    get: async () => { throw new Error('不应逐项读取'); },
  });
  await monitor.refresh();
  assert.equal(monitor.getState().activeTasks.length, 101);
  assert.deepEqual(pages, [1, 2]);
});
