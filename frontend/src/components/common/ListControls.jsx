import React from 'react';
import { Search } from 'lucide-react';

export function ListFilters({ query, onQuery, sort, onSort }) {
  return <div className="flex flex-wrap items-center gap-2">
    <label className="relative min-w-0 flex-1">
      <Search aria-hidden="true" size={15} className="pointer-events-none absolute left-3 top-3 text-zinc-500" />
      <input aria-label="搜索节目" type="search" value={query} onChange={event => onQuery(event.target.value)} placeholder="搜索节目" className="w-full rounded-lg border border-zinc-800 bg-zinc-900 py-2 pl-9 pr-3 text-sm text-zinc-200 focus:border-indigo-500 focus:outline-none sm:w-52" />
    </label>
    <select aria-label="节目排序" value={sort} onChange={event => onSort(event.target.value)} className="rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-300">
      <option value="published_desc">最新发布</option><option value="published_asc">最早发布</option><option value="title_asc">标题顺序</option>
    </select>
  </div>;
}

export function ListPagination({ list }) {
  return <div className="flex flex-col items-center gap-3 px-4 py-5">
    {list.error && <div role="alert" className="flex items-center gap-3 text-sm text-red-300"><span>{list.error}</span><button onClick={() => list.pagination.has_next && list.data.length ? list.loadMore() : list.reload()} className="rounded-lg border border-red-800 px-3 py-2">重试</button></div>}
    {list.loading && <p role="status" className="text-sm text-zinc-500">正在加载…</p>}
    {list.pagination.has_next && !list.loading && <button onClick={list.loadMore} className="rounded-lg border border-zinc-700 bg-zinc-900 px-5 py-2 text-sm text-zinc-300 hover:text-white">加载更多</button>}
    {!list.loading && !list.error && list.data.length > 0 && <p className="text-xs text-zinc-500">已显示 {list.data.length} / {list.pagination.total}</p>}
  </div>;
}
