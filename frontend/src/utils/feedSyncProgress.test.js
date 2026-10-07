import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createInstance } from 'i18next';
import { localizeFeedProgress } from './feedSyncProgress.js';
import { createFeedRefreshAction } from './taskActions.js';

test('视频同步和文稿进度随中英文切换，未知来源错误保持原文', async () => {
  const resources = Object.fromEntries(['zh', 'en'].map(language => [language, {
    translation: JSON.parse(readFileSync(new URL(`../locales/${language}.json`, import.meta.url))),
  }]));
  const i18n = createInstance();
  await i18n.init({ lng: 'zh', resources });
  assert.equal(localizeFeedProgress('后台获取文稿 1/15', i18n.t), '后台获取文稿 1/15');
  assert.equal(localizeFeedProgress('后台补齐节目资料 2/15', i18n.t), '后台补齐节目资料 2/15');
  await i18n.changeLanguage('en');
  assert.equal(localizeFeedProgress('后台获取文稿 1/15', i18n.t), 'Fetching transcripts in the background 1/15');
  assert.equal(localizeFeedProgress('视频列表已更新：新增 15 期', i18n.t), 'Video list updated: 15 new episodes');
  assert.equal(localizeFeedProgress('文稿已更新：12 期，暂不可用 3 期', i18n.t), 'Transcripts updated: 12 episodes, 3 unavailable');
  assert.equal(localizeFeedProgress('后台补齐节目资料 2/15', i18n.t), 'Completing episode details in the background 2/15');
  assert.equal(localizeFeedProgress('节目资料更新完成；新增文稿 0 期，暂不可用 0 期', i18n.t), 'Episode details updated: 0 new transcripts, 0 unavailable');
  assert.equal(localizeFeedProgress('Provider error 429', i18n.t), 'Provider error 429');
});

test('同一订阅连续刷新只提交一次，完成后可再次刷新', async () => {
  let submissions = 0;
  let resolve;
  const notices = [];
  const refresh = createFeedRefreshAction({
    refresh: () => { submissions++; return new Promise(done => { resolve = done; }); },
    onQueued: task => notices.push(task.task_id),
    onError: error => { throw error; },
  });
  const first = refresh('channel');
  assert.equal(refresh('channel'), first);
  await Promise.resolve();
  assert.equal(submissions, 1);
  resolve({ data: { task_id: 'first' } });
  await first;
  const second = refresh('channel');
  await Promise.resolve();
  assert.equal(submissions, 2);
  resolve({ data: { task_id: 'second' } });
  await second;
  assert.deepEqual(notices, ['first', 'second']);
});
