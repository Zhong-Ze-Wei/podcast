// -*- coding: utf-8 -*-
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Download, LayoutGrid, List } from 'lucide-react';
import EpisodeCard from '../cards/EpisodeCard';

/**
 * DownloadedView - 已下载页面
 * 仅显示downloaded状态，不包括已转录
 */
const DownloadedView = ({ episodes, feeds, onEpisodeClick, onPlay, onStar, viewMode = 'grid', onViewModeChange }) => {
  const { t } = useTranslation();

  // 只过滤 downloaded 状态的节目
  const downloadedEpisodes = episodes.filter(ep => ep.status === 'downloaded');

  // 创建feed图片映射
  const feedImageMap = {};
  (feeds || []).forEach(f => { feedImageMap[f.id] = f.image; });

  return (
    <div className="flex flex-col h-full bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* 头部 */}
      <div className="px-8 py-6 border-b border-zinc-800 bg-zinc-900/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-600 flex items-center justify-center shadow-xl">
              <Download size={32} className="text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-white">{t('downloaded.title')}</h1>
              <p className="text-zinc-400 text-sm mt-1">
                {downloadedEpisodes.length} {t('downloaded.episodes')}
              </p>
            </div>
          </div>
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

      {/* 列表 */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-8">
        {downloadedEpisodes.length > 0 ? (
          <div className={`grid ${viewMode === 'list' ? 'grid-cols-1 gap-3' : 'grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4'}`}>
            {downloadedEpisodes.map(ep => (
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
        ) : (
          <div className="flex flex-col items-center justify-center py-20 text-zinc-500">
            <Download size={48} className="mb-4 text-zinc-700" />
            <p className="text-lg font-medium mb-2">{t('downloaded.empty')}</p>
            <p className="text-sm text-zinc-600">{t('downloaded.emptyHint')}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default DownloadedView;
