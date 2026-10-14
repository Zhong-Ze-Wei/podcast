import test from 'node:test';
import assert from 'node:assert/strict';
import { parseAppPath } from './appRoutes.js';

test('最近更新有独立地址，刷新和返回时能恢复页面', () => {
  assert.deepEqual(parseAppPath('/recent'), { type: 'view', view: 'recent' });
  assert.deepEqual(parseAppPath('/recent/'), { type: 'view', view: 'recent' });
  assert.deepEqual(parseAppPath('/episodes'), { type: 'view', view: 'list' });
  assert.deepEqual(parseAppPath('/feeds/feed-1'), { type: 'feed', id: 'feed-1' });
});
