export function getBriefingTaskPeriod(task) {
  if (task.type !== 'briefing-report') return null;
  const period = task.report_period || task.result?.period;
  if (!period || !['week', 'month'].includes(period.type) || !/^\d{4}-\d{2}-\d{2}$/.test(period.start || '')) return null;
  const date = new Date(`${period.start}T00:00:00Z`);
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== period.start) return null;
  return { type: period.type, start: period.start };
}

export function briefingTaskLabel(task, language = 'zh') {
  const period = getBriefingTaskPeriod(task);
  if (!period) return '';
  const date = new Date(`${period.start}T00:00:00Z`);
  const english = language.startsWith('en');
  if (period.type === 'month') {
    return english
      ? `${new Intl.DateTimeFormat('en-US', { year: 'numeric', month: 'long', timeZone: 'UTC' }).format(date)} · Monthly report`
      : `${date.getUTCFullYear()}年${date.getUTCMonth() + 1}月 · 月报`;
  }
  const last = new Date(date.getTime() + 6 * 86400000).toISOString().slice(0, 10);
  const end = last.slice(0, 4) === period.start.slice(0, 4) ? last.slice(5) : last;
  return `${period.start.replaceAll('-', '.')} — ${end.replaceAll('-', '.')} · ${english ? 'Weekly report' : '周报'}`;
}

export function briefingTaskNavigation(task) {
  const period = getBriefingTaskPeriod(task);
  if (!period) return null;
  const modes = Object.keys(task.result?.reports || {});
  return { periodType: period.type, periodStart: period.start, mode: modes.length === 1 ? modes[0] : 'core' };
}
