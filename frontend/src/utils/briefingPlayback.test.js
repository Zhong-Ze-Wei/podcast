import test from 'node:test';
import assert from 'node:assert/strict';
import { getPlaybackPosition, getExternalPlaybackUrl } from './briefingPlayback.js';

test('字幕时间覆盖上次进度，零秒保持有效', () => {
  assert.equal(getPlaybackPosition({ play_position: 900 }, 42.5), 42.5);
  assert.equal(getPlaybackPosition({ play_position: 900 }, 0), 0);
  assert.equal(getPlaybackPosition({ play_position: 900 }), 900);
});

test('YouTube 链接保留视频与其他参数，并替换旧起播时间', () => {
  const url = new URL(getExternalPlaybackUrl({ link: 'https://www.youtube.com/watch?v=episode&t=1s&list=playlist' }, 123.9));
  assert.equal(url.searchParams.get('v'), 'episode');
  assert.equal(url.searchParams.get('list'), 'playlist');
  assert.equal(url.searchParams.get('t'), '123s');
});

test('视频 GUID 可生成原平台链接，B站保留字幕时间', () => {
  assert.equal(getExternalPlaybackUrl({ guid: 'youtube:episode' }, 0), 'https://www.youtube.com/watch?v=episode&t=0s');
  assert.equal(getExternalPlaybackUrl({ guid: 'bilibili:BVexample' }, 2495.479), 'https://www.bilibili.com/video/BVexample?t=2495');
});

test('文章链接保持原样，未知时间不产生错误的起播参数', () => {
  assert.equal(getExternalPlaybackUrl({ link: 'https://example.com/post?ref=podcast' }, 100), 'https://example.com/post?ref=podcast');
  assert.equal(getExternalPlaybackUrl({ link: 'https://youtu.be/episode' }, null), 'https://youtu.be/episode');
});

test('非公开网页地址不能成为外部收听链接', () => {
  assert.equal(getExternalPlaybackUrl({ link: 'javascript:alert(1)' }, 50), '');
  assert.equal(getExternalPlaybackUrl({ guid: 'internal-id' }, 50), '');
});
