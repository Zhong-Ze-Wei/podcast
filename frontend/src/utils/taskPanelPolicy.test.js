import test from 'node:test';
import assert from 'node:assert/strict';
import { shouldAutoOpenTaskPanel } from './taskPanelPolicy.js';

test('手机新后台任务不打断阅读，任务仍可由页头主动打开', () => {
  assert.equal(shouldAutoOpenTaskPanel({ mobile:true, activeCount:1, previousActiveCount:0, userClosed:false }),false);
});

test('桌面首次出现活动任务可打开，但用户手动关闭和后续轮询不反复打断', () => {
  assert.equal(shouldAutoOpenTaskPanel({ mobile:false, activeCount:1, previousActiveCount:0, userClosed:false }),true);
  assert.equal(shouldAutoOpenTaskPanel({ mobile:false, activeCount:1, previousActiveCount:0, userClosed:true }),false);
  assert.equal(shouldAutoOpenTaskPanel({ mobile:false, activeCount:2, previousActiveCount:1, userClosed:false }),false);
});
