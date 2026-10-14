// 用于 App 的订阅同步入口；同一订阅的连续点击共享一次提交。
export function createFeedRefreshAction({ refresh, onQueued, onError }) {
  const pending = new Map();
  return feedId => {
    if (pending.has(feedId)) return pending.get(feedId);
    const request = Promise.resolve().then(() => refresh(feedId))
      .then(response => {
        onQueued(response.data, feedId);
        return response.data;
      })
      .catch(error => { onError(error); })
      .finally(() => { pending.delete(feedId); });
    pending.set(feedId, request);
    return request;
  };
}

export const isActiveTask = task => ['pending', 'processing'].includes(task.status);
export const isTerminalTask = task => ['completed', 'failed', 'cancelled'].includes(task.status);
export const canCancelTask = task => isActiveTask(task) && task.can_cancel === true && !task.cancel_requested;

export async function requestTaskCancellation(taskId, { cancel, refresh, onError }) {
  try {
    await cancel(taskId);
    await refresh();
  } catch (error) {
    onError(error);
  }
}

// 相同终态在轮询中只通知一次，避免重复刷新已保存结果。
export function createTerminalNotifier(onTerminal) {
  const notified = new Set();
  return task => {
    if (!isTerminalTask(task) || notified.has(task.id)) return;
    notified.add(task.id);
    onTerminal(task);
  };
}
