import test from 'node:test';
import assert from 'node:assert/strict';
import { briefingTaskLabel } from './briefingTask.js';
import { getTaskNavigation } from './taskNavigation.js';

test('单篇任务即使带周期也打开对应节目的 AI 解读，不跳到周报', () => {
  const task = { type: 'briefing-report', episode_id: 'episode-1', target_exists: true,
    report_period: { type: 'week', start: '2026-09-28' },
    report_context: { kind: 'reading', source_id: 'epepisode-1' } };
  assert.equal(briefingTaskLabel(task), '');
  assert.deepEqual(getTaskNavigation(task), { type: 'episode', id: 'episode-1', tab: 'analysis' });
  task.status = 'completed';
  assert.deepEqual(getTaskNavigation(task), { type: 'episode', id: 'episode-1', tab: 'analysis' });
});

test('独立文稿没有节目记录时打开单篇阅读，并保留已知周期', () => {
  const task = { type: 'briefing-report', report_context: { kind: 'reading', source_id: 'S01' } };
  assert.deepEqual(getTaskNavigation(task), { type: 'briefing', readingSource: 'S01' });
  task.report_period = { type: 'month', start: '2026-09-01' };
  assert.deepEqual(getTaskNavigation(task), { type: 'briefing', readingSource: 'S01', periodType: 'month', periodStart: '2026-09-01' });
});

test('单篇任务没有关联内容或对应节目已删除时不提供错误跳转', () => {
  const task = { type: 'briefing-report', report_context: { kind: 'reading' } };
  assert.equal(getTaskNavigation(task), null);
  Object.assign(task, { episode_id: 'episode-1', target_exists: false, report_period: { type: 'month', start: '2026-09-01' } });
  assert.equal(getTaskNavigation(task), null);
});

test('进行中的月报任务打开对应月份和正在生成的内容模式', () => {
  const task = { type: 'briefing-report', status: 'processing', report_period: { type: 'month', start: '2026-09-01' }, report_context: { kind: 'modes', mode: 'quotes' } };
  assert.deepEqual(getTaskNavigation(task), { type: 'briefing', periodType: 'month', periodStart: '2026-09-01', mode: 'quotes' });
  assert.equal(briefingTaskLabel(task), '2026年9月 · 月报');
});

test('下载和订阅任务保留原有跳转，删除的目标不能打开', () => {
  assert.deepEqual(getTaskNavigation({ type: 'download', target_type: 'episode', target_id: 'episode-1' }), { type: 'episode', id: 'episode-1' });
  assert.deepEqual(getTaskNavigation({ type: 'refresh', target_type: 'feed', target_id: 'feed-1' }), { type: 'feed', id: 'feed-1' });
  assert.equal(getTaskNavigation({ type: 'download', target_type: 'episode', target_id: 'episode-1', target_exists: false }), null);
});
