import test from 'node:test';
import assert from 'node:assert/strict';
import { briefingTaskLabel, briefingTaskNavigation } from './briefingTask.js';

test('九月月报任务显示九月，点击回到九月对应内容模式', () => {
  const task = { type: 'briefing-report', report_period: { type: 'month', start: '2026-09-01' }, result: { reports: { quotes: { id: 'quote-report' } } } };
  assert.equal(briefingTaskLabel(task), '2026年9月 · 月报');
  assert.equal(briefingTaskLabel(task, 'en'), 'September 2026 · Monthly report');
  assert.deepEqual(briefingTaskNavigation(task), { periodType: 'month', periodStart: '2026-09-01', mode: 'quotes' });
});

test('跨月和跨年周报显示完整范围，不依赖任务创建时间', () => {
  const task = { type: 'briefing-report', created_at: '2026-10-01', report_period: { type: 'week', start: '2026-09-28' } };
  assert.equal(briefingTaskLabel(task), '2026.09.28 — 10.04 · 周报');
  task.report_period.start = '2026-12-28';
  assert.equal(briefingTaskLabel(task), '2026.12.28 — 2027.01.03 · 周报');
});

test('旧完成任务从生成结果读取周期，缺周期时不猜月份', () => {
  const task = { type: 'briefing-report', result: { period: { type: 'month', start: '2026-10-01' } } };
  assert.equal(briefingTaskLabel(task), '2026年10月 · 月报');
  assert.equal(briefingTaskLabel({ type: 'briefing-report', created_at: '2026-09-01' }), '');
  assert.equal(briefingTaskNavigation({ type: 'summarize' }), null);
  task.result.period.start = '2026-02-30';
  assert.equal(briefingTaskNavigation(task), null);
});
