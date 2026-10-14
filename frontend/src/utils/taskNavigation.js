import { briefingTaskNavigation, getBriefingTaskPeriod } from './briefingTask.js';

export function getTaskNavigation(task) {
  if (task.type === 'briefing-report' && task.report_context?.kind === 'reading') {
    if (task.target_exists === false && task.episode_id) return null;
    if (task.episode_id) return { type: 'episode', id: task.episode_id, tab: 'analysis' };
    const sourceId = task.report_context.source_id;
    if (!sourceId) return null;
    const period = getBriefingTaskPeriod(task);
    return { type: 'briefing', readingSource: sourceId, ...(period ? { periodType: period.type, periodStart: period.start } : {}) };
  }
  const briefing = briefingTaskNavigation(task);
  if (briefing) return { type: 'briefing', ...briefing };
  if (task.target_id && task.target_type && task.target_exists !== false) {
    return { type: task.target_type, id: task.target_id };
  }
  return null;
}
