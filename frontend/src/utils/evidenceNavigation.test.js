import test from 'node:test';
import assert from 'node:assert/strict';
import { evidenceIndex, evidenceSwipeStep, evidenceGallery, evidenceFor } from './evidenceNavigation.js';

test('原话横向拖拽按方向切换，短点击和纵向阅读不翻页', () => {
  assert.equal(evidenceSwipeStep(-90, 12), 1);
  assert.equal(evidenceSwipeStep(85, 10), -1);
  assert.equal(evidenceSwipeStep(-30, 2), 0);
  assert.equal(evidenceSwipeStep(90, 100), 0);
  assert.equal(evidenceSwipeStep(75, 60), 0);
});

test('原话首尾卡片停止，不循环到无关的另一端；单卡不能翻页', () => {
  assert.equal(evidenceIndex(0, -1, 4), 0);
  assert.equal(evidenceIndex(3, 1, 4), 3);
  assert.equal(evidenceIndex(1, 1, 4), 2);
  assert.equal(evidenceIndex(0, 1, 1), 0);
});

test('从当前观点定位到全篇原话卡组，同源同句只显示一次并保留各自出处', () => {
  const first = { source_id: 'e1', quote: '第一段' };
  const second = { source_id: 'e2', quote: '第二段' };
  const selection = evidenceGallery({ title: '第二个议题', quotes: [second] }, [
    { title: '第一个议题', quote: first },
    { title: '第二个议题', evidence: [second] },
    { ...first, kind: 'quote' },
  ]);
  assert.equal(selection.quotes.length, 2);
  assert.equal(selection.initialIndex, 1);
  assert.equal(selection.quotes[0].context_title, '第一个议题');
  assert.equal(selection.quotes[1].source_id, 'e2');
});

test('单篇议题的多个原文段落全部可查看，已展开的周报依据不会重复', () => {
  const second = { source_id: 'episode', quote: '后半段的条件', offset: 900 };
  const first = { source_id: 'episode', quote: '前半段的论点', offset: 0, supporting_references: [second] };
  assert.deepEqual(evidenceFor({ quote: first }), [first, second]);
  assert.deepEqual(evidenceFor({ evidence: [first, second] }), [first, second]);
  const gallery = evidenceGallery({ title: '完整论点', quotes: evidenceFor({ quote: first }) }, [{ quote: first }]);
  assert.equal(gallery.quotes.length, 2);
  assert.equal(gallery.quotes[1].offset, 900);
});
