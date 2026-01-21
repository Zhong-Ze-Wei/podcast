// -*- coding: utf-8 -*-
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Play, ChevronLeft, Globe, RefreshCw, Rss, Clock, Plus, LayoutGrid, List, Loader2 } from 'lucide-react';
import { decodeHtmlEntities } from '../../utils/helpers';
import EpisodeCard from '../cards/EpisodeCard';

/**
 * FeedDetailView - 订阅源详情页
 * 显示订阅源信息和其所有节目列表
 */
const FeedDetailView = ({ feed, episodes, loading = false, onBack, onRefresh, onEpisodeClick, onPlay, onStar, viewMode = 'grid', onViewModeChange }) => {
  const { t } = useTranslation();
  const [showFullDesc, setShowFullDesc] = useState(false);

  if (!feed) return null;

  const description = decodeHtmlEntities(feed.description) || '';
  const isLongDesc = description.length > 200;

  return (
    <div className="flex flex-col h-full bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* 头部区域 */}
      <div className="px-8 py-6 border-b border-zinc-800 bg-zinc-900/20">
        <div className="flex items-start gap-6">
          <button onClick={onBack} className="mt-1 p-2 hover:bg-zinc-800 rounded-full transition-colors text-zinc-400 hover:text-white">
            <ChevronLeft size={24} />
          </button>

          {/* 封面 */}
          <img
            src={feed.image || '/placeholder.png'}
            alt={feed.title}
            className="w-32 h-32 rounded-2xl object-cover shadow-xl shadow-black/50"
            onError={(e) => {
              if (!e.target.dataset.fallback) {
                e.target.dataset.fallback = 'true';
                e.target.src = '/placeholder.png';
              }
            }}
          />

          {/* 信息区 */}
          <div className="flex-1 min-w-0">
            <h1 className="text-3xl font-bold text-white mb-2 leading-tight">{feed.title}</h1>

            <div className="flex items-center gap-3 mb-4 text-sm">
              <span className="text-indigo-400 font-semibold">{feed.author || t('feed.unknownAuthor')}</span>
              {feed.language && (
                <>
                  <span className="w-1 h-1 rounded-full bg-zinc-600"></span>
                  <span className="text-zinc-500">{feed.language}</span>
                </>
              )}
            </div>

            {/* 操作按钮 */}
            <div className="flex items-center gap-3 mb-4">
              <button
                onClick={() => episodes[0] && onPlay(episodes[0])}
                disabled={!episodes.length}
                className="flex items-center gap-2 bg-white text-black px-5 py-2 rounded-full font-semibold hover:scale-105 transition-transform shadow-lg shadow-white/10 disabled:opacity-50 disabled:hover:scale-100"
              >
                <Play size={16} fill="currentColor" stroke="none" /> {t('feedDetail.playLatest')}
              </button>

              {feed.website && (
                <a
                  href={feed.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-4 py-2 border border-zinc-700 rounded-full text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors"
                >
                  <Globe size={14} /> {t('feedDetail.visitWebsite')}
                </a>
              )}

              <button
                onClick={() => onRefresh(feed.id)}
                className="flex items-center gap-2 px-4 py-2 border border-zinc-700 rounded-full text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors"
              >
                <RefreshCw size={14} /> {t('episode.refresh')}
              </button>
            </div>

            {/* 简介 */}
            {description && (
              <div className="text-sm text-zinc-400 leading-relaxed">
                <p className={showFullDesc ? '' : 'line-clamp-2'}>
                  {description}
                </p>
                {isLongDesc && (
                  <button
                    onClick={() => setShowFullDesc(!showFullDesc)}
                    className="text-indigo-400 hover:text-indigo-300 text-xs mt-1"
                  >
                    {showFullDesc ? t('feedDetail.showLess') : t('feedDetail.showMore')}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* 统计信息 */}
        <div className="flex items-center gap-6 mt-6 ml-14 text-sm text-zinc-500">
          <span className="flex items-center gap-2">
            <Rss size={14} className="text-indigo-400" />
            {feed.episode_count} {t('episode.episodes')}
          </span>
          {feed.last_updated && (
            <span className="flex items-center gap-2">
              <Clock size={14} />
              {t('feedDetail.lastUpdated')}: {new Date(feed.last_updated).toLocaleDateString()}
            </span>
          )}
          {feed.created_at && (
            <span className="flex items-center gap-2">
              <Plus size={14} />
              {t('feedDetail.subscribedAt')}: {new Date(feed.created_at).toLocaleDateString()}
            </span>
          )}
        </div>
      </div>

      {/* 节目列表区域 */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {/* 置顶工具栏 */}
        <div className="sticky top-0 z-10 bg-zinc-950/95 backdrop-blur-sm px-8 py-4 border-b border-zinc-800/50">
          <div className="flex items-center justify-between">
            <p className="text-sm text-zinc-400">
              {loading ? t('common.loading') : `${episodes.length} ${t('episode.episodes')}`}
            </p>
            {/* 视图切换按钮 */}
            <div className="flex bg-zinc-800 rounded-xl p-1">
              <button
                onClick={() => onViewModeChange && onViewModeChange('grid')}
                className={`p-2 rounded-lg transition-colors ${viewMode === 'grid' ? 'bg-zinc-700 text-white' : 'text-zinc-400 hover:text-white'}`}
                title={t('view.grid')}
              >
                <LayoutGrid size={16} />
              </button>
              <button
                onClick={() => onViewModeChange && onViewModeChange('list')}
                className={`p-2 rounded-lg transition-colors ${viewMode === 'list' ? 'bg-zinc-700 text-white' : 'text-zinc-400 hover:text-white'}`}
                title={t('view.list')}
              >
                <List size={16} />
              </button>
            </div>
          </div>
        </div>
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="animate-spin text-indigo-500" size={32} />
          </div>
        ) : (
          <div className={`p-8 grid ${viewMode === 'list' ? 'grid-cols-1 gap-3' : 'grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4'}`}>
            {episodes.map(ep => (
              <EpisodeCard
                key={ep.id}
                episode={ep}
                onClick={onEpisodeClick}
                onStar={onStar}
                onPlay={onPlay}
                viewMode={viewMode}
                feedImage={feed.image}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default FeedDetailView;
