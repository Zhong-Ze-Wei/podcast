// -*- coding: utf-8 -*-
import React from 'react';
import { Play, Star } from 'lucide-react';
import StatusBadge from '../common/StatusBadge';

/**
 * EpisodeCard - 节目卡片组件
 * 支持网格/列表双视图
 */
const EpisodeCard = ({ episode, onClick, onStar, onPlay, viewMode = 'grid', feedImage }) => {
  // 获取封面图片：优先单集图片，fallback 到 feed 图片
  const coverImage = episode.image || feedImage || '/placeholder.png';

  // 网格视图 - 大封面卡片
  if (viewMode === 'grid') {
    return (
      <div
        onClick={() => onClick(episode)}
        className="group bg-zinc-900/40 border border-zinc-800/50 hover:bg-zinc-800/60 hover:border-zinc-700/80 rounded-2xl overflow-hidden transition-all duration-300 cursor-pointer flex flex-col hover:shadow-xl hover:shadow-black/50"
      >
        {/* 封面图片 - 使用 3:2 比例 */}
        <div className="relative aspect-[3/2] overflow-hidden">
          <img
            src={coverImage}
            alt={episode.title}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
            onError={(e) => {
              if (!e.target.dataset.fallback) {
                e.target.dataset.fallback = 'true';
                e.target.src = '/placeholder.png';
              }
            }}
          />
          {/* 悬停播放按钮 */}
          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
            <button
              onClick={(e) => { e.stopPropagation(); onPlay && onPlay(episode); }}
              className="w-12 h-12 rounded-full bg-white flex items-center justify-center text-black hover:scale-110 transition-transform shadow-xl"
            >
              <Play size={24} fill="currentColor" stroke="none" className="ml-1" />
            </button>
          </div>
          {/* 时长标签 */}
          {episode.duration_formatted && (
            <div className="absolute bottom-2 right-2 bg-black/70 px-2 py-1 rounded text-xs text-white">
              {episode.duration_formatted}
            </div>
          )}
        </div>

        {/* 信息区 */}
        <div className="p-4 flex flex-col flex-1">
          <div className="flex items-start justify-between gap-2 mb-2">
            <h3 className="text-sm font-semibold text-zinc-100 line-clamp-2 leading-snug group-hover:text-white flex-1">
              {episode.title}
            </h3>
            <button
              onClick={(e) => { e.stopPropagation(); onStar(episode); }}
              className={`p-1 rounded transition-colors flex-shrink-0 ${episode.is_starred ? 'text-yellow-400' : 'text-zinc-600 hover:text-yellow-400'}`}
            >
              <Star size={14} fill={episode.is_starred ? 'currentColor' : 'none'} />
            </button>
          </div>

          <p className="text-xs text-indigo-400 font-medium mb-2">{episode.feed_title}</p>

          <div className="flex items-center justify-between text-xs text-zinc-500 mt-auto">
            <span>{episode.published_at && new Date(episode.published_at).toLocaleDateString()}</span>
            <StatusBadge status={episode.status} hasTranscript={episode.has_transcript} hasSummary={episode.has_summary} />
          </div>
        </div>
      </div>
    );
  }

  // 列表视图 - 紧凑横向
  return (
    <div
      onClick={() => onClick(episode)}
      className="group flex items-center gap-4 p-3 bg-zinc-900/40 border border-zinc-800/50 hover:bg-zinc-800/60 hover:border-zinc-700/80 rounded-xl cursor-pointer transition-all"
    >
      {/* 封面缩略图 */}
      <div className="relative w-16 h-16 rounded-lg overflow-hidden flex-shrink-0">
        <img
          src={coverImage}
          alt={episode.title}
          className="w-full h-full object-cover"
          onError={(e) => {
            if (!e.target.dataset.fallback) {
              e.target.dataset.fallback = 'true';
              e.target.src = '/placeholder.png';
            }
          }}
        />
        {/* 悬停播放 */}
        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <button
            onClick={(e) => { e.stopPropagation(); onPlay && onPlay(episode); }}
            className="w-8 h-8 rounded-full bg-white flex items-center justify-center text-black"
          >
            <Play size={14} fill="currentColor" stroke="none" className="ml-0.5" />
          </button>
        </div>
      </div>

      {/* 内容区 */}
      <div className="flex-1 min-w-0">
        <h3 className="text-sm font-medium text-zinc-100 truncate group-hover:text-white">
          {episode.title}
        </h3>
        <p className="text-xs text-indigo-400 mt-0.5">{episode.feed_title}</p>
        <p className="text-xs text-zinc-500 mt-1">
          {episode.published_at && new Date(episode.published_at).toLocaleDateString()}
          {episode.duration_formatted && ` - ${episode.duration_formatted}`}
        </p>
      </div>

      {/* 右侧操作区 */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <button
          onClick={(e) => { e.stopPropagation(); onStar(episode); }}
          className={`p-1.5 rounded-lg transition-colors ${episode.is_starred ? 'text-yellow-400' : 'text-zinc-600 hover:text-yellow-400'}`}
        >
          <Star size={16} fill={episode.is_starred ? 'currentColor' : 'none'} />
        </button>
        <StatusBadge status={episode.status} hasTranscript={episode.has_transcript} hasSummary={episode.has_summary} />
      </div>
    </div>
  );
};

export default EpisodeCard;
