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
