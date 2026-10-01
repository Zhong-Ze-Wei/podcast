// -*- coding: utf-8 -*-
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Star } from 'lucide-react';
import EpisodeCard from '../cards/EpisodeCard';
import ViewToolbar from '../common/ViewToolbar';
import { episodesApi } from '../../services/api';
import usePaginatedList from '../../hooks/usePaginatedList';
import useDebouncedValue from '../../hooks/useDebouncedValue';
import { ListFilters, ListPagination } from '../common/ListControls';

/**
 * FavoritesView - 我的喜欢页面
 * 显示所有标星的节目
 */
const FavoritesView = ({ refreshVersion, feeds, onEpisodeClick, onPlay, onStar, viewMode = 'grid', onViewModeChange }) => {
  const { t } = useTranslation();

  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('published_desc');
  const q = useDebouncedValue(query);
  const list = usePaginatedList(episodesApi.list, { params: { is_starred: true, q, sort }, revision: refreshVersion });
  const starredEpisodes = list.data;

  // 创建feed图片映射
  const feedImageMap = {};
  (feeds || []).forEach(f => { feedImageMap[f.id] = f.image; });

  return (
    <div className="flex flex-col h-full bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* 头部 */}
      <div className="px-8 py-6 border-b border-zinc-800 bg-zinc-900/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-yellow-500 to-orange-600 flex items-center justify-center shadow-xl">
              <Star size={32} className="text-white" fill="currentColor" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-white">{t('favorites.title')}</h1>
              <p className="text-zinc-400 text-sm mt-1">
                {list.pagination.total} {t('favorites.episodes')}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* 列表 */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <ViewToolbar
          count={`${list.pagination.total} ${t('favorites.episodes')}`}
          description={t('viewToolbar.favoritesDescription')}
          viewMode={viewMode}
          onViewModeChange={onViewModeChange}
        ><ListFilters query={query} onQuery={setQuery} sort={sort} onSort={setSort} /></ViewToolbar>
        {starredEpisodes.length > 0 ? (
          <div className={`p-8 grid ${viewMode === 'list' ? 'grid-cols-1 gap-3' : 'grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4'}`}>
            {starredEpisodes.map(ep => (
              <EpisodeCard
                key={ep.id}
                episode={ep}
                onClick={onEpisodeClick}
                onStar={onStar}
                onPlay={onPlay}
                viewMode={viewMode}
                feedImage={feedImageMap[ep.feed_id]}
              />
            ))}
          </div>
        ) : !list.loading && !list.error ? (
          <div className="flex flex-col items-center justify-center py-20 text-zinc-500">
            <Star size={48} className="mb-4 text-zinc-700" />
            <p className="text-lg font-medium mb-2">{t('favorites.empty')}</p>
            <p className="text-sm text-zinc-600">{t('favorites.emptyHint')}</p>
          </div>
        ) : null}
        <ListPagination list={list} />
      </div>
    </div>
  );
};

export default FavoritesView;
