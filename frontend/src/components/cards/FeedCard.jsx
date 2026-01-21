// -*- coding: utf-8 -*-
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Rss, RefreshCw, Heart } from 'lucide-react';
import { decodeHtmlEntities } from '../../utils/helpers';

/**
 * FeedCard - 订阅源卡片组件
 * 支持网格/列表双视图
 */
const FeedCard = ({ feed, onClick, onRefresh, viewMode = 'grid' }) => {
  const { t } = useTranslation();

  // 网格视图
  if (viewMode === 'grid') {
    return (
      <div
        onClick={() => onClick(feed)}
        className="group bg-zinc-900/40 border border-zinc-800/50 hover:bg-zinc-800/60 hover:border-zinc-700/80 rounded-2xl overflow-hidden transition-all duration-300 cursor-pointer flex flex-col hover:shadow-xl hover:shadow-black/50"
      >
        {/* 封面图片 - 使用 3:2 比例 */}
        <div className="relative aspect-[3/2] overflow-hidden">
          <img
            src={feed.image || '/placeholder.png'}
            alt={feed.title}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
            onError={(e) => {
              if (!e.target.dataset.fallback) {
                e.target.dataset.fallback = 'true';
                e.target.src = '/placeholder.png';
              }
            }}
          />
          {/* 节目数量角标 */}
          <div className="absolute bottom-2 right-2 bg-black/70 px-2 py-1 rounded text-xs text-white">
            {feed.episode_count} {t('episode.episodes')}
          </div>
          {/* 收藏标记 */}
          {feed.is_favorite && (
            <div className="absolute top-2 right-2">
              <Heart size={16} className="text-pink-400" fill="currentColor" />
            </div>
          )}
        </div>

        {/* 信息区 */}
        <div className="p-4 flex flex-col flex-1">
          <h3 className="text-sm font-semibold text-zinc-100 line-clamp-2 leading-snug group-hover:text-white mb-1">
            {feed.title}
          </h3>
          <p className="text-xs text-indigo-400 font-medium mb-2">{feed.author || t('feed.unknownAuthor')}</p>
          <p className="text-xs text-zinc-500 line-clamp-2 flex-1">{decodeHtmlEntities(feed.description) || t('episode.noDescription')}</p>
          <div className="flex items-center justify-between text-xs text-zinc-500 mt-3 pt-2 border-t border-zinc-800/50">
            <span className="flex items-center gap-1.5">
              <Rss size={12} /> {feed.language || 'Unknown'}
            </span>
            <button
              onClick={(e) => { e.stopPropagation(); onRefresh(feed.id); }}
              className="flex items-center gap-1.5 text-zinc-400 hover:text-indigo-400 transition-colors"
            >
              <RefreshCw size={12} />
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 列表视图
  return (
    <div
      onClick={() => onClick(feed)}
      className="group flex items-center gap-4 p-3 bg-zinc-900/40 border border-zinc-800/50 hover:bg-zinc-800/60 hover:border-zinc-700/80 rounded-xl cursor-pointer transition-all"
    >
      {/* 封面缩略图 */}
      <div className="relative w-16 h-16 rounded-lg overflow-hidden flex-shrink-0">
        <img
          src={feed.image || '/placeholder.png'}
          alt={feed.title}
          className="w-full h-full object-cover"
          onError={(e) => {
            if (!e.target.dataset.fallback) {
              e.target.dataset.fallback = 'true';
              e.target.src = '/placeholder.png';
            }
          }}
        />
        {feed.is_favorite && (
          <div className="absolute top-1 right-1">
            <Heart size={10} className="text-pink-400" fill="currentColor" />
          </div>
        )}
      </div>

      {/* 内容区 */}
      <div className="flex-1 min-w-0">
        <h3 className="text-sm font-medium text-zinc-100 truncate group-hover:text-white">
          {feed.title}
        </h3>
        <p className="text-xs text-indigo-400 mt-0.5">{feed.author || t('feed.unknownAuthor')}</p>
        <p className="text-xs text-zinc-500 mt-1">
          {feed.episode_count} {t('episode.episodes')} - {feed.language || 'Unknown'}
        </p>
      </div>

      {/* 右侧操作区 */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <button
          onClick={(e) => { e.stopPropagation(); onRefresh(feed.id); }}
          className="p-1.5 rounded-lg text-zinc-600 hover:text-indigo-400 transition-colors"
        >
          <RefreshCw size={16} />
        </button>
      </div>
    </div>
  );
};

export default FeedCard;
