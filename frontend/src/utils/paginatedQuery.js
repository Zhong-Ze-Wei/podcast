export const EMPTY_PAGE = { page: 0, per_page: 24, total: 0, has_next: false };

// 页面列表共用这一请求边界，旧页面响应不能覆盖当前查询。
export function createPaginatedQuery(request, onChange = () => {}, perPage = 24, onLoaded) {
  let state = { data: [], pagination: { ...EMPTY_PAGE, per_page: perPage }, loading: false, error: '' };
  let params = {};
  let version = 0;
  let disposed = false;
  let pending = null;
  const publish = next => { state = next; if (!disposed) onChange(state); };
  const load = async ({ append = false, preserve = false } = {}) => {
    if (disposed) return state;
    const current = ++version;
    const nextPage = append ? state.pagination.page + 1 : 1;
    publish({ ...state, data: append || preserve ? state.data : [], loading: true, error: '' });
    try {
      const response = await request({ ...params, page: nextPage, per_page: perPage });
      if (disposed || current !== version) return state;
      const data = append ? [...new Map([...state.data, ...response.data].map(item => [item.id ?? item.item_id, item])).values()] : response.data;
      publish({ data, pagination: response.pagination, loading: false, error: '' });
      onLoaded?.(response);
    } catch (error) {
      if (!disposed && current === version) publish({ ...state, loading: false, error: error.message });
    }
    return state;
  };
  return {
    getState: () => state,
    setParams: next => { disposed = false; params = next; pending = load(); return pending; },
    reload: () => { pending = load({ preserve: true }); return pending; },
    loadMore: () => {
      if (state.loading) return pending;
      if (!state.pagination.has_next) return Promise.resolve(state);
      pending = load({ append: true });
      return pending;
    },
    update: (id, changes) => publish({ ...state, data: state.data.map(item => item.id === id ? { ...item, ...changes } : item) }),
    clear: () => { version += 1; publish({ data: [], pagination: { ...EMPTY_PAGE, per_page: perPage }, loading: false, error: '' }); },
    dispose: () => { disposed = true; version += 1; },
  };
}
