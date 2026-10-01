import test from 'node:test';
import { parseAppPath } from './appRoutes.js';
import assert from 'node:assert/strict';
import { briefingPath, readBriefingRoute, captureReadingPosition, restoreReadingPosition, settingsReturnContext, mergeBriefingNavigation } from './readingContext.js';

test('简报链接完整保留周期、内容模式、标签和单篇阅读，可独立刷新', () => {
  const context = { periodType: 'month', periodStart: '2026-09-01', mode: 'quotes', selectedTag: 'AI', showAll: true, readingSource: 'source-9' };
  const path = briefingPath('reports', context);
  assert.deepEqual(readBriefingRoute(path.split('?')[1]), context);
  assert.equal(briefingPath('saved', context).split('?')[0], '/briefing/saved');
});

test('设置返回保留当前产品模式和阅读位置；旧简报设置归入同一设置入口', () => {
  const reading = { periodType: 'week', periodStart: '2026-09-21', mode: 'concepts', selectedTag: '编程', showAll: true, scroll: { top: 740, itemId: 'item-7', offset: -40 } };
  const context = settingsReturnContext('briefing', 'ai-briefing', reading, '/briefing');
  assert.equal(context.mode, 'ai-briefing');
  assert.equal(context.view, 'briefing');
  assert.deepEqual(context.briefing.scroll, reading.scroll);
  assert.match(context.path, /mode=concepts/);
  assert.equal(settingsReturnContext('feedDetail', 'traditional', null, '/feeds/f1').path, '/feeds/f1');
});

test('阅读位置使用可见条目和偏移，在字体或排版变化后仍返回同一句附近', () => {
  const cards = [ {dataset:{itemId:'a'},getBoundingClientRect:()=>({top:-80,bottom:10})}, {dataset:{itemId:'b'},getBoundingClientRect:()=>({top:20,bottom:120})} ];
  let top;
  const container = { scrollTop: 600, getBoundingClientRect:()=>({top:10}), querySelectorAll:()=>cards, scrollTo:value=>{top=value.top;} };
  const position = captureReadingPosition(container);
  assert.deepEqual(position, {top:600,itemId:'b',offset:10});
  container.querySelectorAll = ()=>[{dataset:{itemId:'b'},getBoundingClientRect:()=>({top:80,bottom:180})}];
  restoreReadingPosition(container,position);
  assert.equal(top,660);
  container.querySelectorAll = ()=>[];
  restoreReadingPosition(container,position);
  assert.equal(top,600);
});

test('旧简报设置与实验路由进入统一设置 AI 分类，节目详情仍为直观详情页', () => {
  assert.deepEqual(parseAppPath('/briefing/settings'), {type:'view',view:'settings',section:'briefing',mode:'ai-briefing'});
  assert.deepEqual(parseAppPath('/briefing-lab/settings'), {type:'view',view:'settings',section:'briefing',mode:'ai-briefing'});
  assert.deepEqual(parseAppPath('/episodes/e1'), {type:'episode',id:'e1'});
});

test('任务导航切换月报时显式周期起点优先；侧栏只选择类型时回到该类型当前周期', () => {
  const current = {periodType:'week',periodStart:'2026-09-21',mode:'core'};
  assert.equal(mergeBriefingNavigation(current,{periodType:'month',periodStart:'2026-09-01',mode:'quotes'}).periodStart,'2026-09-01');
  assert.equal(mergeBriefingNavigation(current,{periodType:'month'}).periodStart,null);
  assert.equal(mergeBriefingNavigation(current,{mode:'concepts'}).periodStart,'2026-09-21');
});
