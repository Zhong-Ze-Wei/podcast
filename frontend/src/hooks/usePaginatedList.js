import { useEffect, useMemo, useRef, useState } from 'react';
import { createPaginatedQuery } from '../utils/paginatedQuery';

// request 必须稳定（API 方法或 useCallback）；params 改变从第一页重新查询。
export default function usePaginatedList(request, { params = {}, enabled = true, revision = 0, perPage = 24, scope = '', onLoaded } = {}) {
  const [state, setState] = useState({ data: [], pagination: { total: 0, has_next: false }, loading: false, error: '' });
  const query = useMemo(() => createPaginatedQuery(request, setState, perPage, onLoaded), [request, perPage, scope, onLoaded]);
  const paramsKey = JSON.stringify(params);
  const revisionRef = useRef(revision);
  useEffect(() => {
    if (!enabled) { query.clear(); return; }
    let active = true;
    // StrictMode 会立即清理第一次 effect，等清理结束后只发送仍有效的查询。
    queueMicrotask(() => {
      if (active) query.setParams(JSON.parse(paramsKey));
    });
    return () => { active = false; query.dispose(); };
  }, [query, enabled, paramsKey]);
  useEffect(() => {
    if (revisionRef.current === revision) return;
    revisionRef.current = revision;
    if (enabled) query.reload();
  }, [query, enabled, revision]);
  return { ...state, reload: query.reload, loadMore: query.loadMore, update: query.update, clear: query.clear };
}
