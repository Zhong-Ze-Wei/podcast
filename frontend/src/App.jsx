// -*- coding: utf-8 -*-
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, RefreshCw } from 'lucide-react';
import { feedsApi, episodesApi, tasksApi, capabilitiesApi } from './services/api';
import {
  AUTO_REFRESH_KEY,
  TASK_POLL_KEY,
  TASK_HISTORY_WINDOW_KEY,
  TASK_PANEL_DEFAULT_OPEN_KEY
} from './components/views/settings/AppSettingsPanel';
// Layout components
import Sidebar from './components/layout/Sidebar';
// View components
import EpisodeDetailView from './components/views/EpisodeDetailView';
import FeedDetailView from './components/views/FeedDetailView';
import FavoritesView from './components/views/FavoritesView';
import WorkspaceView from './components/views/WorkspaceView';
import SettingsView from './components/views/SettingsView';
import TranscriptionView from './components/views/TranscriptionView';
import AIBriefingView from './components/views/AIBriefingView';
// Card components
import FeedCard from './components/cards/FeedCard';
import EpisodeCard from './components/cards/EpisodeCard';
// Common components
import LanguageSwitcher from './components/common/LanguageSwitcher';
import ViewToolbar from './components/common/ViewToolbar';
// Player components
import PlayerBar from './components/player/PlayerBar';
// Task components
import TaskPanel from './components/tasks/TaskPanel';

const SIMPLE_VIEW_PATHS = {
  list: '/episodes',
  workspace: '/workspace',
  favorites: '/favorites',
  settings: '/settings',
  transcription: '/transcription'
};

function parseAppPath(pathname) {
  const parts = pathname.split('/').filter(Boolean);
  if (parts[0] === 'episodes' && parts[1]) {
    return { type: 'episode', id: parts[1] };
  }
  if (parts[0] === 'feeds' && parts[1]) {
    return { type: 'feed', id: parts[1] };
  }
  if (parts[0] === 'episodes') return { type: 'view', view: 'list' };
  if (parts[0] === 'favorites') return { type: 'view', view: 'favorites' };
  if (parts[0] === 'settings') return { type: 'view', view: 'settings' };
  if (parts[0] === 'transcription') return { type: 'view', view: 'transcription' };
  return { type: 'view', view: 'workspace' };
}

function episodePath(id) {
  return `/episodes/${id}`;
}

function feedPath(id) {
  return `/feeds/${id}`;
}

export default function App() {
  const { t } = useTranslation();
  const [view, setView] = useState('workspace'); // list | feedDetail | detail | workspace
  const [previousView, setPreviousView] = useState('workspace'); // 记录进入详情页之前的视图，用于返回
  const [viewMode, setViewMode] = useState('traditional'); // 'traditional' | 'ai-briefing'
  const [activeFeed, setActiveFeed] = useState(null);
  const [selectedFeed, setSelectedFeed] = useState(null); // 用于FeedDetailView
  const [selectedEpisode, setSelectedEpisode] = useState(null);
  const [currentPlaying, setCurrentPlaying] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [feeds, setFeeds] = useState([]);
  const [episodes, setEpisodes] = useState([]);
  const [workspaceEpisodes, setWorkspaceEpisodes] = useState([]); // 已转录/已摘要的episodes
  const [feedEpisodes, setFeedEpisodes] = useState([]); // 当前选中feed的全部episodes
  const [feedEpisodesLoading, setFeedEpisodesLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [capabilities, setCapabilities] = useState(null);
  const [capabilitiesLoading, setCapabilitiesLoading] = useState(false);
  const [capabilitiesError, setCapabilitiesError] = useState('');
  const refreshCapabilities = useCallback(async () => {
    setCapabilitiesLoading(true);
    try {
      const response = await capabilitiesApi.get();
      setCapabilities(response.data);
      setCapabilitiesError('');
    } catch {
      setCapabilities(null);
      setCapabilitiesError('settings.transcription.loadError');
    } finally {
      setCapabilitiesLoading(false);
    }
  }, []);
  useEffect(() => {
    refreshCapabilities();
    window.addEventListener('focus', refreshCapabilities);
    return () => window.removeEventListener('focus', refreshCapabilities);
  }, [refreshCapabilities]);
  const [searchQuery, setSearchQuery] = useState('');
  const [episodeViewMode, setEpisodeViewMode] = useState('grid'); // grid | list
  const audioRef = useRef(null);
  const getPlayableAudioUrl = (episode) => episode?.local_audio_url || episode?.audio_url || '';
  const lastSavedPositionRef = useRef(0); // 上次保存的位置，避免频繁保存
  const feedRequestIdRef = useRef(0); // 用于取消过期的feed episodes请求
  const hasInAppNavigationRef = useRef(false);
  const latestViewRef = useRef(view);

  useEffect(() => {
    latestViewRef.current = view;
  }, [view]);

  // 保存播放位置到后端
  const savePlayPosition = async (episodeId, position) => {
    if (!episodeId || position === undefined) return;
    // 只在位置变化超过5秒时保存
    if (Math.abs(position - lastSavedPositionRef.current) < 5) return;
    try {
      await episodesApi.update(episodeId, { play_position: Math.floor(position) });
      lastSavedPositionRef.current = position;
    } catch (err) {
      console.error('Failed to save play position:', err);
    }
  };

  // 定期保存播放位置 (每30秒)
  useEffect(() => {
    if (!currentPlaying || !isPlaying) return;
    const interval = setInterval(() => {
      if (audioRef.current && currentPlaying) {
        savePlayPosition(currentPlaying.id, audioRef.current.currentTime);
      }
    }, 30000);
    return () => clearInterval(interval);
  }, [currentPlaying, isPlaying]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [feedsData, episodesData, transcribedData] = await Promise.all([
        feedsApi.list(),
        episodesApi.list({ per_page: 500 }),
        episodesApi.listTranscribed()
      ]);
      setFeeds(feedsData.data || feedsData);
      setEpisodes(episodesData.data || episodesData);
      setWorkspaceEpisodes(transcribedData.data || transcribedData);
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // 自动刷新间隔（分钟，来自 localStorage）
  const [autoRefreshMinutes, setAutoRefreshMinutes] = useState(
    () => parseInt(localStorage.getItem(AUTO_REFRESH_KEY) ?? '5', 10)
  );
  const [taskPollSeconds, setTaskPollSeconds] = useState(
    () => parseInt(localStorage.getItem(TASK_POLL_KEY) ?? '3', 10)
  );
  const [taskHistoryWindowMinutes, setTaskHistoryWindowMinutes] = useState(
    () => parseInt(localStorage.getItem(TASK_HISTORY_WINDOW_KEY) ?? '60', 10)
  );
  const [taskPanelDefaultOpen, setTaskPanelDefaultOpen] = useState(
    () => localStorage.getItem(TASK_PANEL_DEFAULT_OPEN_KEY) === 'true'
  );

  // 监听设置变更（同一窗口内通过 dispatchEvent 传递）
  useEffect(() => {
    const handleStorage = (e) => {
      if (e.key === AUTO_REFRESH_KEY) setAutoRefreshMinutes(parseInt(e.newValue ?? '5', 10));
      if (e.key === TASK_POLL_KEY)    setTaskPollSeconds(parseInt(e.newValue ?? '3', 10));
      if (e.key === TASK_HISTORY_WINDOW_KEY) setTaskHistoryWindowMinutes(parseInt(e.newValue ?? '60', 10));
      if (e.key === TASK_PANEL_DEFAULT_OPEN_KEY) setTaskPanelDefaultOpen(e.newValue === 'true');
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  // 定时自动刷新订阅内容（0 = 关闭）
  useEffect(() => {
    if (!autoRefreshMinutes) return;
    const timer = setInterval(loadData, autoRefreshMinutes * 60 * 1000);
    return () => clearInterval(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefreshMinutes]);

  const handleAddFeed = () => {
    loadData();
  };

  const handleRefreshFeed = () => {
    loadData();
  };

  const handleDeleteFeed = () => {
    setActiveFeed(null);
    setSelectedFeed(null);
    loadData();
  };

  const updateBrowserPath = useCallback((path, { replace = false, state = {} } = {}) => {
    if (!path || window.location.pathname === path) return;
    if (!replace) hasInAppNavigationRef.current = true;
    const method = replace ? 'replaceState' : 'pushState';
    window.history[method]({ appRoute: true, ...state }, '', path);
  }, []);

  const navigateToView = useCallback((nextView, { replace = false } = {}) => {
    setActiveFeed(null);
    setSelectedFeed(null);
    setSelectedEpisode(null);
    setFeedEpisodes([]);
    setView(nextView);
    updateBrowserPath(SIMPLE_VIEW_PATHS[nextView] || SIMPLE_VIEW_PATHS.workspace, {
      replace,
      state: { view: nextView }
    });
  }, [updateBrowserPath]);

  const openEpisode = useCallback(async (episodeOrId, { replace = false, push = true } = {}) => {
    const episodeId = typeof episodeOrId === 'string' ? episodeOrId : episodeOrId?.id;
    if (!episodeId) return;

    if (push) {
      updateBrowserPath(episodePath(episodeId), {
        replace,
        state: { view: 'detail', episodeId }
      });
    }

    setPreviousView(latestViewRef.current === 'detail' ? previousView : latestViewRef.current);
    if (typeof episodeOrId !== 'string') {
      setSelectedEpisode(episodeOrId);
    }
    setView('detail');

    try {
      const response = await episodesApi.get(episodeId);
      const episode = response.data || response;
      setSelectedEpisode(episode);
      if (episode?.feed_id) setActiveFeed(episode.feed_id);
    } catch (err) {
      console.error('Failed to open episode route:', err);
      navigateToView('workspace', { replace: true });
    }
  }, [navigateToView, previousView, updateBrowserPath]);

  const openFeed = useCallback(async (feedOrId, { replace = false, push = true } = {}) => {
    const feedId = typeof feedOrId === 'string' ? feedOrId : feedOrId?.id;
    if (!feedId) return;

    if (push) {
      updateBrowserPath(feedPath(feedId), {
        replace,
        state: { view: 'feedDetail', feedId }
      });
    }

    setActiveFeed(feedId);
    setView('feedDetail');
    setFeedEpisodes([]);
    setFeedEpisodesLoading(true);

    const requestId = ++feedRequestIdRef.current;

    try {
      let feed = typeof feedOrId === 'string' ? feeds.find(item => item.id === feedId) : feedOrId;
      if (!feed) {
        const feedResponse = await feedsApi.get(feedId);
        feed = feedResponse.data || feedResponse;
      }
      setSelectedFeed(feed);

      const response = await feedsApi.getEpisodes(feedId, { per_page: 500 });
      if (requestId === feedRequestIdRef.current) {
        const episodeData = response.data || response;
        setFeedEpisodes(Array.isArray(episodeData) ? episodeData : []);
        setFeedEpisodesLoading(false);
      }
    } catch (err) {
      if (requestId === feedRequestIdRef.current) {
        console.error('Failed to open feed route:', err);
        setFeedEpisodes([]);
        setFeedEpisodesLoading(false);
      }
      navigateToView('workspace', { replace: true });
    }
  }, [feeds, navigateToView, updateBrowserPath]);

  const applyCurrentPath = useCallback((replace = true) => {
    const route = parseAppPath(window.location.pathname);
    if (route.type === 'episode') {
      openEpisode(route.id, { replace, push: false });
      return;
    }
    if (route.type === 'feed') {
      openFeed(route.id, { replace, push: false });
      return;
    }
    navigateToView(route.view, { replace });
  }, [navigateToView, openEpisode, openFeed]);

  useEffect(() => {
    window.history.replaceState(
      { ...(window.history.state || {}), appRoute: true },
      '',
      window.location.pathname
    );
    applyCurrentPath(true);

    const handlePopState = () => {
      applyCurrentPath(true);
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 点击订阅源卡片，进入详情页
  const handleFeedClick = async (feed) => {
    openFeed(feed);
  };

  const handleEpisodeClick = async (episode) => {
    openEpisode(episode);
  };

  const handleStar = async (episode) => {
    const newStarred = !episode.is_starred;

    // 乐观更新：立即更新所有状态
    const updateEpisodeList = (list) =>
      list.map(ep => ep.id === episode.id ? {...ep, is_starred: newStarred} : ep);

    setEpisodes(prev => updateEpisodeList(prev));
    setFeedEpisodes(prev => updateEpisodeList(prev));
    setWorkspaceEpisodes(prev => updateEpisodeList(prev));

    try {
      await episodesApi.star(episode.id, newStarred);
    } catch (err) {
      console.error('Star failed:', err);
      // 失败时回滚
      const rollback = (list) =>
        list.map(ep => ep.id === episode.id ? {...ep, is_starred: !newStarred} : ep);
      setEpisodes(prev => rollback(prev));
      setFeedEpisodes(prev => rollback(prev));
      setWorkspaceEpisodes(prev => rollback(prev));
    }
  };

  // 订阅源收藏处理（乐观更新）
  const handleStarFeed = async (feed) => {
    const newFavorite = !feed.is_favorite;

    // 乐观更新：立即更新 feeds 状态
    setFeeds(prev =>
      prev.map(f => f.id === feed.id ? {...f, is_favorite: newFavorite} : f)
    );

    // 更新 selectedFeed（如果当前选中的是这个feed）
    if (selectedFeed && selectedFeed.id === feed.id) {
      setSelectedFeed(prev => ({...prev, is_favorite: newFavorite}));
    }

    try {
      await feedsApi.favorite(feed.id, { favorite: newFavorite });
    } catch (err) {
      console.error('Favorite failed:', err);
      // 失败时回滚
      setFeeds(prev =>
        prev.map(f => f.id === feed.id ? {...f, is_favorite: !newFavorite} : f)
      );
      if (selectedFeed && selectedFeed.id === feed.id) {
        setSelectedFeed(prev => ({...prev, is_favorite: !newFavorite}));
      }
    }
  };

  // 播放控制函数
  const handlePlay = (episode) => {
    if (currentPlaying?.id === episode.id) {
      // 如果是同一个episode，切换播放/暂停
      handlePlayPause(!isPlaying);
    } else {
      // 切换episode前保存当前播放位置
      if (currentPlaying && audioRef.current) {
        savePlayPosition(currentPlaying.id, audioRef.current.currentTime);
      }
      // 重置位置记录
      lastSavedPositionRef.current = episode.play_position || 0;
      // 播放新的episode
      setCurrentPlaying({
        ...episode,
        playable_audio_url: getPlayableAudioUrl(episode)
      });
      setIsPlaying(true);
      // 等待下一个渲染周期，audio元素更新后再播放
      setTimeout(() => {
        if (audioRef.current) {
          // 恢复播放位置
          if (episode.play_position && episode.play_position > 0) {
            audioRef.current.currentTime = episode.play_position;
          }
          audioRef.current.play().catch(err => console.error('Play failed:', err));
        }
      }, 100);
    }
  };

  const handlePlayPause = (playing) => {
    setIsPlaying(playing);
    if (audioRef.current) {
      if (playing) {
        audioRef.current.play().catch(err => console.error('Play failed:', err));
      } else {
        // 暂停时保存播放位置
        if (currentPlaying) {
          savePlayPosition(currentPlaying.id, audioRef.current.currentTime);
        }
        audioRef.current.pause();
      }
    }
  };

  const handleSeek = (time) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time;
    }
  };

  const handleAudioError = () => {
    if (!currentPlaying) return;

    const canFallbackToRemote =
      currentPlaying.playable_audio_url &&
      currentPlaying.audio_url &&
      currentPlaying.playable_audio_url !== currentPlaying.audio_url;

    if (!canFallbackToRemote) {
      console.error('Audio playback failed:', currentPlaying.title || currentPlaying.id);
      setIsPlaying(false);
      return;
    }

    setCurrentPlaying(prev => prev ? {
      ...prev,
      playable_audio_url: prev.audio_url,
      local_audio_failed: true
    } : prev);

    setTimeout(() => {
      if (audioRef.current && isPlaying) {
        audioRef.current.play().catch(err => console.error('Play failed:', err));
      }
    }, 100);
  };

  const filteredEpisodes = episodes.filter(ep => {
    const matchesFeed = !activeFeed || ep.feed_id === activeFeed;
    const matchesSearch = !searchQuery ||
      ep.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ep.description?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFeed && matchesSearch;
  });

  if (loading && feeds.length === 0) {
    return (
      <div className="flex h-screen items-center justify-center bg-black text-zinc-100">
        <div className="text-center">
          <RefreshCw className="animate-spin mx-auto mb-4 text-indigo-500" size={32} />
          <p className="text-zinc-400">{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-black text-zinc-100 font-sans selection:bg-indigo-500/30 overflow-hidden">
      <Sidebar
        feeds={feeds}
        activeFeed={activeFeed}
        setActiveFeed={setActiveFeed}
        setSelectedFeed={setSelectedFeed}
        setView={navigateToView}
        onAddFeed={handleAddFeed}
        onRefreshFeed={handleRefreshFeed}
        onDeleteFeed={handleDeleteFeed}
        onStarFeed={handleStarFeed}
        onNoteFeed={loadData}
        onFeedClick={handleFeedClick}
        hasPlayer={!!currentPlaying}
        currentView={view}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
      />

      <div className="flex-1 flex flex-col min-w-0 bg-black relative">
        <div className="absolute top-0 left-0 w-full h-96 bg-indigo-900/10 pointer-events-none blur-3xl rounded-full translate-y-[-50%]"></div>

        <div className="absolute top-4 right-8 z-20">
          <LanguageSwitcher />
        </div>

        {/* AI简报模式 */}
        {viewMode === 'ai-briefing' && view === 'list' ? (
          <AIBriefingView
            onEpisodeClick={handleEpisodeClick}
            onPlay={handlePlay}
          />
        ) : view === 'list' ? (
          <div className="flex-1 overflow-y-auto custom-scrollbar z-10">
            <div className="px-8 py-6 border-b border-zinc-800 bg-zinc-900/20">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-3xl font-bold text-white">
                    {activeFeed ? feeds.find(f => f.id === activeFeed)?.title : t('sidebar.subscriptions')}
                  </h2>
                  <p className="text-zinc-500 text-sm mt-1">
                    {activeFeed
                      ? `${filteredEpisodes.length} ${t('episode.episodes')}`
                      : `${feeds.length} ${t('feed.subscriptions')}`
                    }
                  </p>
                </div>
                <div className="flex gap-3">
                  {activeFeed && (
                    <div className="relative group">
                      <Search className="absolute left-3 top-2.5 text-zinc-500 group-focus-within:text-indigo-400 transition-colors" size={18} />
                      <input
                        type="text"
                        placeholder={t('episode.searchPlaceholder')}
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="bg-zinc-900 border border-zinc-800 rounded-xl pl-10 pr-4 py-2 text-sm text-zinc-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 w-64 transition-all"
                      />
                    </div>
                  )}
                  <button
                    onClick={() => loadData()}
                    className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-xl text-sm font-medium transition-colors"
                  >
                    <RefreshCw size={16} />
                  </button>
                </div>
              </div>
            </div>

            <ViewToolbar
              count={activeFeed
                ? `${filteredEpisodes.length} ${t('episode.episodes')}`
                : `${feeds.length} ${t('feed.subscriptions')}`}
              description={activeFeed ? t('viewToolbar.feedDescription') : t('viewToolbar.subscriptionsDescription')}
              viewMode={episodeViewMode}
              onViewModeChange={setEpisodeViewMode}
            />

            <div className={`p-8 grid ${episodeViewMode === 'list' ? 'grid-cols-1 gap-3' : 'grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4'} ${currentPlaying ? 'pb-24' : ''}`}>
              {activeFeed ? (
                // 显示选中Feed的Episodes
                filteredEpisodes.map(ep => (
                  <EpisodeCard
                    key={ep.id}
                    episode={ep}
                    onClick={handleEpisodeClick}
                    onStar={handleStar}
                    onPlay={handlePlay}
                    viewMode={episodeViewMode}
                    feedImage={activeFeed?.image}
                  />
                ))
              ) : (
                // 显示所有订阅源卡片
                feeds.map(feed => (
                  <FeedCard
                    key={feed.id}
                    feed={feed}
                    onClick={handleFeedClick}
                    onRefresh={handleRefreshFeed}
                    viewMode={episodeViewMode}
                  />
                ))
              )}
            </div>
          </div>
        ) : view === 'feedDetail' ? (
          <FeedDetailView
            feed={selectedFeed}
            episodes={feedEpisodes}
            loading={feedEpisodesLoading}
            onBack={() => navigateToView('list')}
            onRefresh={handleRefreshFeed}
            onEpisodeClick={handleEpisodeClick}
            onPlay={handlePlay}
            onStar={handleStar}
            viewMode={episodeViewMode}
            onViewModeChange={setEpisodeViewMode}
          />
        ) : view === 'favorites' ? (
          <FavoritesView
            episodes={episodes}
            feeds={feeds}
            onEpisodeClick={handleEpisodeClick}
            onPlay={handlePlay}
            onStar={handleStar}
            viewMode={episodeViewMode}
            onViewModeChange={setEpisodeViewMode}
          />
        ) : view === 'workspace' ? (
          <WorkspaceView
            episodes={workspaceEpisodes}
            feeds={feeds}
            onEpisodeClick={handleEpisodeClick}
            onPlay={handlePlay}
            onStar={handleStar}
            viewMode={episodeViewMode}
            onViewModeChange={setEpisodeViewMode}
          />
        ) : view === 'transcription' ? (
          <TranscriptionView
            capabilities={capabilities}
            loading={capabilitiesLoading}
            error={capabilitiesError ? t(capabilitiesError) : ''}
            onRefresh={refreshCapabilities}
            onBack={() => {
              if (hasInAppNavigationRef.current) window.history.back();
              else navigateToView('workspace');
            }}
          />
        ) : view === 'settings' ? (
          <SettingsView
            onBack={() => navigateToView('list')}
          />
        ) : (
          <EpisodeDetailView
            capabilities={capabilities}
            capabilitiesError={capabilitiesError ? t(capabilitiesError) : ''}
            onOpenTranscription={() => navigateToView('transcription')}
            episode={selectedEpisode}
            onBack={() => {
              if (hasInAppNavigationRef.current) {
                window.history.back();
              } else {
                navigateToView(previousView || 'workspace');
              }
            }}
            onRefresh={loadData}
            onPlay={handlePlay}
          />
        )}
      </div>

      {/* 隐藏的audio元素 */}
      <audio
        ref={audioRef}
        src={currentPlaying?.playable_audio_url || currentPlaying?.audio_url}
        preload="metadata"
        onError={handleAudioError}
      />

      <PlayerBar
        episode={currentPlaying}
        isPlaying={isPlaying}
        onPlayPause={handlePlayPause}
        onSeek={handleSeek}
        audioRef={audioRef}
      />

      {/* 任务进度面板 */}
      <TaskPanel
        onTaskComplete={loadData}
        onNavigate={({ type, id }) => {
          if (type === 'episode') openEpisode(id);
          if (type === 'feed') openFeed(id);
        }}
        pollIntervalMs={taskPollSeconds * 1000}
        historyWindowMinutes={taskHistoryWindowMinutes}
        defaultOpen={taskPanelDefaultOpen}
      />
    </div>
  );
}
