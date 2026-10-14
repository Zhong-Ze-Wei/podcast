import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Clock } from 'lucide-react';
import EpisodeCard from '../cards/EpisodeCard';
import ViewToolbar from '../common/ViewToolbar';
import { ListFilters, ListPagination } from '../common/ListControls';
import { episodesApi } from '../../services/api';
import usePaginatedList from '../../hooks/usePaginatedList';
import useDebouncedValue from '../../hooks/useDebouncedValue';

export default function RecentUpdatesView({ refreshVersion, feeds, onEpisodeClick, onPlay, onStar, viewMode = 'grid', onViewModeChange }) {
  const { t } = useTranslation();
  const [days, setDays] = useState(7);
  const [daysDraft, setDaysDraft] = useState('7');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('published_desc');
  const [readFilter, setReadFilter] = useState('all');
  const q = useDebouncedValue(query);
  const list = usePaginatedList(episodesApi.list, {
    params: { days, q, sort, ...(readFilter !== 'all' ? { is_read: readFilter === 'read' } : {}) },
    revision: refreshVersion,
  });
  const feedImages = Object.fromEntries(feeds.map(feed => [feed.id, feed.image]));
  const applyDays = event => {
    event.preventDefault();
    setDays(Number(daysDraft));
  };

  return <div className="flex h-full flex-col overflow-hidden bg-zinc-950 text-zinc-100">
    <div className="border-b border-zinc-800 bg-zinc-900/20 px-4 py-4 md:px-8 md:py-6">
      <h1 className="text-xl font-bold text-white md:text-3xl">{t('recent.title')}</h1>
      <p className="mt-1 text-sm text-zinc-400">{t('recent.description', { days })}</p>
    </div>
    <div className="flex-1 overflow-y-auto custom-scrollbar">
      <ViewToolbar count={t('recent.count', { count: list.pagination.total })} viewMode={viewMode} onViewModeChange={onViewModeChange}>
        <form onSubmit={applyDays} className="flex items-center gap-2 text-sm text-zinc-400">
          <label htmlFor="recent-days">{t('recent.days')}</label>
          <input id="recent-days" aria-label={t('recent.days')} type="number" min="1" max="3650" step="1" required value={daysDraft} onChange={event => setDaysDraft(event.target.value)} className="w-20 rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-zinc-200 focus:border-indigo-500 focus:outline-none" />
          <button type="submit" className="rounded-lg border border-zinc-700 px-3 py-2 text-zinc-300 hover:bg-zinc-800">{t('recent.apply')}</button>
        </form>
        <ListFilters query={query} onQuery={setQuery} sort={sort} onSort={setSort} readFilter={readFilter} onReadFilter={setReadFilter} />
      </ViewToolbar>
      {list.data.length > 0 ? <div className={`grid p-4 md:p-8 ${viewMode === 'list' ? 'grid-cols-1 gap-3' : 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4'}`}>
        {list.data.map(episode => <EpisodeCard key={episode.id} episode={episode} onClick={onEpisodeClick} onPlay={onPlay} onStar={onStar} viewMode={viewMode} feedImage={feedImages[episode.feed_id]} />)}
      </div> : !list.loading && !list.error ? <div className="flex flex-col items-center gap-3 py-20 text-zinc-500"><Clock size={40} className="text-zinc-700" /><p>{t('recent.empty', { days })}</p></div> : null}
      <ListPagination list={list} />
    </div>
  </div>;
}
