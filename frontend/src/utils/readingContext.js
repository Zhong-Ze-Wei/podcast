const MODES = ['core', 'quotes', 'connections', 'concepts', 'resources'];

export function readBriefingRoute(search) {
  const query = new URLSearchParams(search);
  const type = query.get('period_type');
  const start = query.get('period_start');
  const validStart = /^\d{4}-\d{2}-\d{2}$/.test(start || '') && Number.isFinite(Date.parse(start)) && new Date(start).toISOString().slice(0, 10) === start;
  return { periodType: type === 'month' ? 'month' : 'week', periodStart: validStart ? start : null, mode: MODES.includes(query.get('mode')) ? query.get('mode') : 'core', selectedTag: '', showAll: query.get('all') === '1', readingSource: query.get('source') || null };
}

export function briefingPath(section, context) {
  const query = new URLSearchParams();
  query.set('period_type', context.periodType || 'week');
  if (context.periodStart) query.set('period_start', context.periodStart);
  query.set('mode', context.mode || 'core');
  if (context.showAll) query.set('all', '1');
  if (context.readingSource) query.set('source', context.readingSource);
  return `${section === 'saved' ? '/briefing/saved' : '/briefing'}?${query}`;
}

export function settingsReturnContext(view, mode, briefing, path) {
  const isBriefing = view === 'briefing' || view === 'briefingSaved';
  return { version: 1, mode, view, path: isBriefing ? briefingPath(view === 'briefingSaved' ? 'saved' : 'reports', briefing) : path, briefing: isBriefing ? { ...briefing, scroll: briefing.scroll && { ...briefing.scroll } } : null };
}

export function captureReadingPosition(container) {
  if (!container) return { top: 0 };
  const viewportTop = container.getBoundingClientRect().top;
  const item = [...container.querySelectorAll('[data-item-id]')].find(card => card.getBoundingClientRect().bottom > viewportTop);
  return { top: container.scrollTop, ...(item ? { itemId: item.dataset.itemId, offset: item.getBoundingClientRect().top - viewportTop } : {}) };
}

export function restoreReadingPosition(container, position) {
  if (!container || !position) return;
  const item = [...container.querySelectorAll('[data-item-id]')].find(card => card.dataset.itemId === position.itemId);
  const top = item ? container.scrollTop + item.getBoundingClientRect().top - container.getBoundingClientRect().top - position.offset : position.top;
  container.scrollTo({ top, behavior: 'instant' });
}

export function mergeBriefingNavigation(current, options) {
  return { ...current, readingSource: null, showAll: false, ...options, ...(options.periodType && options.periodType !== current.periodType && !Object.hasOwn(options, 'periodStart') ? { periodStart: null } : {}) };
}
