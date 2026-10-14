import { localizeUiMessage } from './utils/localization';
// -*- coding: utf-8 -*-
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw } from 'lucide-react';
import { authApi, feedsApi, episodesApi, setAuthToken } from './services/api';
import {
  AUTO_REFRESH_KEY,
  TASK_POLL_KEY,
  TASK_HISTORY_WINDOW_KEY,
  TASK_PANEL_DEFAULT_OPEN_KEY
} from './components/views/settings/AppSettingsPanel';
// Layout components
import Sidebar from './components/layout/Sidebar';
import MobileHeader from './components/layout/MobileHeader';
// View components
import EpisodeDetailView from './components/views/EpisodeDetailView';
import FeedDetailView from './components/views/FeedDetailView';
import FavoritesView from './components/views/FavoritesView';
import WorkspaceView from './components/views/WorkspaceView';
import RecentUpdatesView from './components/views/RecentUpdatesView';
import SettingsView from './components/views/SettingsView';
import BriefingReportsView from './components/views/BriefingReportsView';
import { getExternalPlaybackUrl, getPlaybackPosition } from './utils/briefingPlayback';
import { parseAppPath } from './utils/appRoutes';
import { readBriefingRoute, briefingPath, settingsReturnContext, mergeBriefingNavigation } from './utils/readingContext';
import { createFeedRefreshAction } from './utils/taskActions';
import AuthView from './components/views/AuthView';
// Card components
import FeedCard from './components/cards/FeedCard';
// Common components
import LanguageSwitcher from './components/common/LanguageSwitcher';
import ViewToolbar from './components/common/ViewToolbar';
import { ListPagination } from './components/common/ListControls';
import usePaginatedList from './hooks/usePaginatedList';
// Player components
import PlayerBar from './components/player/PlayerBar';
// Task components
import TaskPanel from './components/tasks/TaskPanel';
import { TasksProvider } from './components/tasks/TasksContext';

const SIMPLE_VIEW_PATHS = {
  list: '/episodes',
  workspace: '/workspace',
  favorites: '/favorites',
  recent: '/recent',
  settings: '/settings',
  briefing: '/briefing',
  briefingSaved: '/briefing/saved',
  briefingSettings: '/briefing/settings'
};


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
  const [viewMode, setViewMode] = useState('traditional');
  const [briefingNavigation, setBriefingNavigation] = useState(null);
  const briefingContextRef = useRef({ periodType: 'week', periodStart: null, mode: 'core', selectedTag: '', showAll: false, readingSource: null, scroll: { top: 0 } });
  const [returnContext, setReturnContext] = useState(null);
  const [settingsTab, setSettingsTab] = useState('account');
  const [briefingState, setBriefingState] = useState({ periodType: 'week', mode: 'core' });
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false); // 'traditional' | 'ai-briefing'
  const [activeFeed, setActiveFeed] = useState(null);
  const [selectedFeed, setSelectedFeed] = useState(null); // 用于FeedDetailView
  const [selectedEpisode, setSelectedEpisode] = useState(null);
  const [episodeTab, setEpisodeTab] = useState('transcript');
  const [episodeOpenVersion, setEpisodeOpenVersion] = useState(0);
  const [currentPlaying, setCurrentPlaying] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [authLoading, setAuthLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState(null);
  const [episodeViewMode, setEpisodeViewMode] = useState('grid'); // grid | list
  const audioRef = useRef(null);
  const pendingPlaybackRef = useRef(null);
  const reportPlaybackRef = useRef(null);
  const [playbackNotice, setPlaybackNotice] = useState(null);
  const [actionNotice, setActionNotice] = useState(null);
  const [queuedTask, setQueuedTask] = useState(null);
  const [taskOpenRequest, setTaskOpenRequest] = useState(0);
  const currentUserIdRef = useRef(currentUser?.id);
  currentUserIdRef.current = currentUser?.id;
  // YouTube 视频剧集没有直链音频，走后端在线流代理；其余优先本地文件、其次原始地址
  const getPlayableAudioUrl = (episode) => {
    if (episode?.local_audio_url) return episode.local_audio_url;
    if (episode?.audio_type?.startsWith('video/youtube')) {
      return episodesApi.getStreamUrl(episode.id);
    }
    return episode?.local_audio_url || episode?.audio_url || '';
  };
  const lastSavedPositionRef = useRef(0); // 上次保存的位置，避免频繁保存
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

  const feedList = usePaginatedList(feedsApi.list, { enabled: !authLoading && Boolean(currentUser), scope: currentUser?.id });
  const feeds = feedList.data;
  const loading = feedList.loading;
  const loadData = useCallback(() => {
    feedList.reload();
    setRefreshVersion(version => version + 1);
  }, [feedList.reload]);

  const handleTaskComplete = useCallback((tasks) => {
    if (tasks.some(task => ['refresh', 'fetch_transcripts', 'subscribe'].includes(task.type))) feedList.reload();
    setRefreshVersion(version => version + 1);
    if (selectedFeed && tasks.some(task => task.feed_id === selectedFeed.id)) {
      feedsApi.get(selectedFeed.id).then(response => setSelectedFeed(response.data)).catch(error => setActionNotice({ message: error.message, error: true }));
    }
    if (selectedEpisode && tasks.some(task => task.episode_id === selectedEpisode.id || (task.type === 'fetch_transcripts' && task.feed_id === selectedEpisode.feed_id))) {
      episodesApi.get(selectedEpisode.id).then(response => setSelectedEpisode(response.data)).catch(error => setActionNotice({ message: error.message, error: true }));
    }
  }, [feedList.reload, selectedFeed, selectedEpisode]);

  const handleTaskProgress = useCallback(tasks => {
    if (tasks.some(task => task.type === 'subscribe' && task.progress >= 70)) feedList.reload();
    if (selectedFeed && tasks.some(task => task.feed_id === selectedFeed.id)) setRefreshVersion(version => version + 1);
    if (selectedEpisode && tasks.some(task => task.feed_id === selectedEpisode.feed_id)) {
      episodesApi.get(selectedEpisode.id).then(response => setSelectedEpisode(response.data)).catch(error => setActionNotice({ message: error.message, error: true }));
    }
  }, [feedList.reload, selectedFeed, selectedEpisode]);

  useEffect(() => {
    if (!currentUser) return;
    const visible = () => { if (!document.hidden) loadData(); };
    document.addEventListener('visibilitychange', visible);
    return () => document.removeEventListener('visibilitychange', visible);
  }, [currentUser?.id, loadData]);

  useEffect(() => {
    let mounted = true;
    authApi.me()
      .then((response) => {
        if (!mounted) return;
        const payload = response.data || response;
        setCurrentUser(payload.user);
      })
      .catch(() => {
        if (!mounted) return;
        setCurrentUser(null);
      })
      .finally(() => {
        if (mounted) setAuthLoading(false);
      });
    return () => { mounted = false; };
  }, []);

  const handleAuthenticated = (user) => {
    setCurrentUser(user);
  };

  const handleLogout = () => {
    setAuthToken(null);
    setCurrentUser(null);
    setQueuedTask(null);
    feedList.clear();
    setSelectedEpisode(null);
    setSelectedFeed(null);
    setActiveFeed(null);
  };

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

  // 定时读取已保存的数据（0 = 关闭），订阅源抓取由后端同步任务负责。
  useEffect(() => {
    if (!autoRefreshMinutes) return;
    const timer = setInterval(loadData, autoRefreshMinutes * 60 * 1000);
    return () => clearInterval(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefreshMinutes]);

  const handleAddFeed = data => {
    if (data.task_id) setQueuedTask({ ...data, id: data.task_id });
    loadData();
  };

  const retrySubscription = async url => {
    try {
      const response = await feedsApi.create({ rss_url: url, asynchronous: true });
      handleAddFeed(response.data);
    } catch {
      setActionNotice({ message: t('common.fetchUnavailable'), error: true });
    }
  };

  const handleRefreshFeed = useMemo(() => {
    const owner = currentUser?.id;
    return createFeedRefreshAction({
      refresh: feedId => feedsApi.refresh(feedId),
      onQueued: (task, feedId) => {
        if (currentUserIdRef.current !== owner) return;
        setQueuedTask({ id: task.task_id, type: 'refresh', feed_id: feedId, status: 'pending', progress: 0 });
        setActionNotice({ message: t('feedDetail.syncStarted') });
      },
      onError: () => { if (currentUserIdRef.current === owner) setActionNotice({ message: t('common.fetchUnavailable'), error: true }); },
    });
  }, [currentUser?.id]);

  const handleDeleteFeed = () => {
    setActiveFeed(null);
    setSelectedFeed(null);
    loadData();
  };

  const updateBrowserPath = useCallback((path, { replace = false, state = {} } = {}) => {
    if (!path || window.location.pathname === path || `${window.location.pathname}${window.location.search}` === path) return;
    if (!replace) hasInAppNavigationRef.current = true;
    const method = replace ? 'replaceState' : 'pushState';
    window.history[method]({ appRoute: true, ...state }, '', path);
  }, []);

  const handleBriefingStateChange = useCallback(context => {
    briefingContextRef.current = context;
    setBriefingState(previous => previous.periodType === context.periodType && previous.mode === context.mode ? previous : context);
  }, []);
  useEffect(() => {
    if (!currentUser || !window.location.pathname.startsWith('/settings')) return;
    const stored = sessionStorage.getItem(`podmaster_settings_return:${currentUser.id}`);
    const context = stored ? JSON.parse(stored) : null;
    if (context) { setReturnContext(context); setViewMode(context.mode); }
    const query = new URLSearchParams(window.location.search);
    setSettingsTab(query.get('section') || 'account');
    if (query.get('app_mode') === 'ai-briefing') setViewMode('ai-briefing');
  }, [currentUser?.id]);
  const openSettings = useCallback(({ context, replace = false, section, mode } = {}) => {
    const originMode = mode || viewMode;
    let origin = returnContext;
    if (!replace && latestViewRef.current !== 'settings') {
      origin = settingsReturnContext(latestViewRef.current, originMode, context || briefingContextRef.current, `${window.location.pathname}${window.location.search}`);
      setReturnContext(origin);
      sessionStorage.setItem(`podmaster_settings_return:${currentUser.id}`, JSON.stringify(origin));
    }
    const tab = section || 'account';
    setSettingsTab(tab); setView('settings'); setViewMode(originMode); setMobileSidebarOpen(false);
    updateBrowserPath(`/settings?section=${tab}&app_mode=${originMode}`, { replace, state: { view: 'settings', returnContext: origin } });
  }, [viewMode, returnContext, currentUser?.id, updateBrowserPath]);
  const navigateToView = useCallback((nextView, { replace = false, path, mode } = {}) => {
    if (nextView === 'settings' || nextView === 'briefingSettings') { openSettings({ replace, ...(nextView === 'briefingSettings' ? { section: 'briefing', mode: 'ai-briefing' } : {}) }); return; }
    setActiveFeed(null); setSelectedFeed(null); setSelectedEpisode(null);
    setView(nextView); setViewMode(mode || (nextView.startsWith('briefing') ? 'ai-briefing' : 'traditional'));
    const routePath = SIMPLE_VIEW_PATHS[nextView] || SIMPLE_VIEW_PATHS.workspace;
    const nextPath = path || (nextView.startsWith('briefing') && window.location.pathname.startsWith('/briefing') ? `${routePath}${window.location.search}` : routePath);
    updateBrowserPath(nextPath, { replace, state: { view: nextView } });
  }, [updateBrowserPath, openSettings]);
  const returnFromSettings = () => {
    const context = returnContext;
    if (!context) { navigateToView(viewMode === 'ai-briefing' ? 'briefing' : 'workspace'); return; }
    if (context.briefing) setBriefingNavigation({ ...context.briefing, restore: true });
    updateBrowserPath(context.path, { state: { briefingContext: context.briefing } });
    applyCurrentPath(true);
  };

  // 简报是核心模式切换：切入时把界面带回首屏，避免停在详情/设置页时切换"无感"
  const handleViewModeChange = useCallback((mode) => {
    setViewMode(mode);
    if (mode === 'ai-briefing') {
      navigateToView('briefing');
    } else {
      navigateToView('list');
    }
    setMobileSidebarOpen(false);
  }, [navigateToView]);

  const handleBriefingNavigate = (section, options = {}) => {
    if (section === 'settings') { openSettings({ context: briefingContextRef.current, section: 'briefing' }); return; }
    const context = mergeBriefingNavigation(briefingContextRef.current, options);
    navigateToView(section === 'saved' ? 'briefingSaved' : 'briefing', { path: briefingPath(section, context) });
    setBriefingNavigation({ ...context });
    setMobileSidebarOpen(false);
  };

  const recordEpisodeView = useCallback(async episode => {
    if (episode.is_read) return;
    const owner = currentUserIdRef.current;
    try {
      await episodesApi.read(episode.id, true);
      if (currentUserIdRef.current !== owner) return;
      setSelectedEpisode(previous => previous?.id === episode.id ? { ...previous, is_read: true } : previous);
      setRefreshVersion(version => version + 1);
    } catch (error) {
      if (currentUserIdRef.current === owner) setActionNotice({ message: error.message || t('reading.saveFailed'), error: true });
    }
  }, [t]);

  const openEpisode = useCallback(async (episodeOrId, { replace = false, push = true, tab = 'transcript' } = {}) => {
    const episodeId = typeof episodeOrId === 'string' ? episodeOrId : episodeOrId?.id;
    if (!episodeId) return;

    if (push) {
      updateBrowserPath(`${episodePath(episodeId)}${tab === 'analysis' ? '?tab=analysis' : ''}`, {
        replace,
        state: { view: 'detail', episodeId }
      });
    }

    setPreviousView(latestViewRef.current === 'detail' ? previousView : latestViewRef.current);
    if (typeof episodeOrId !== 'string') {
      setSelectedEpisode(episodeOrId);
    }
    setView('detail');
    setViewMode('traditional');
    setEpisodeTab(tab);

    const owner = currentUserIdRef.current;
    try {
      const response = await episodesApi.get(episodeId);
      const episode = response.data || response;
      if (currentUserIdRef.current !== owner || window.location.pathname !== episodePath(episodeId)) return;
      setSelectedEpisode(episode);
      setEpisodeOpenVersion(version => version + 1);
      if (episode?.feed_id) setActiveFeed(episode.feed_id);
      recordEpisodeView(episode);
      return episode;
    } catch (err) {
      console.error('Failed to open episode route:', err);
      navigateToView('workspace', { replace: true });
    }
  }, [navigateToView, previousView, updateBrowserPath, recordEpisodeView]);

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
    setViewMode('traditional');
    setView('feedDetail');

    try {
      let feed = typeof feedOrId === 'string' ? feeds.find(item => item.id === feedId) : feedOrId;
      if (!feed) {
        const feedResponse = await feedsApi.get(feedId);
        feed = feedResponse.data || feedResponse;
      }
      setSelectedFeed(feed);

    } catch (err) {
      setActionNotice({ message: err.message || t("ui.couldNotLoadThisSubscription"), error: true });
      navigateToView('workspace', { replace: true });
    }
  }, [feeds, navigateToView, updateBrowserPath]);

  const applyCurrentPath = useCallback((replace = true) => {
    const route = parseAppPath(window.location.pathname);
    if (route.type === 'episode') {
      const query = new URLSearchParams(window.location.search);
      const rawTime = query.get('t');
      const startSeconds = rawTime === null ? null : Number(rawTime);
      openEpisode(route.id, { replace, push: false, tab: query.get('tab') === 'analysis' ? 'analysis' : 'transcript' }).then(episode => {
        if (episode && Number.isFinite(startSeconds) && startSeconds >= 0) {
          reportPlaybackRef.current(episode, startSeconds);
        }
      });
      return;
    }
    if (route.type === 'feed') {
      openFeed(route.id, { replace, push: false });
      return;
    }
    if (route.view === 'settings') { const query = new URLSearchParams(window.location.search); openSettings({ replace, section: route.section || query.get('section') || 'account', mode: route.mode || query.get('app_mode') || 'traditional' }); return; }
    if (route.view.startsWith('briefing')) { const context = window.history.state?.briefingContext; setBriefingNavigation(context && context.owner === currentUser?.id ? { ...context, restore: true } : { ...readBriefingRoute(window.location.search) }); }
    navigateToView(route.view, { replace });
  }, [navigateToView, openEpisode, openFeed, openSettings, currentUser?.id]);

  useEffect(() => {
    if (authLoading || !currentUser) return;
    window.history.replaceState(
      { ...(window.history.state || {}), appRoute: true },
      '',
      `${window.location.pathname}${window.location.search}${window.location.hash}`
    );
    applyCurrentPath(true);

    const handlePopState = () => {
      applyCurrentPath(true);
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, currentUser?.id]);

  // 点击订阅源卡片，进入详情页
  const handleFeedClick = async (feed) => {
    openFeed(feed);
  };

  const handleEpisodeClick = async (episode) => {
    openEpisode(episode);
  };

  const handleStar = async (episode) => {
    try {
      await episodesApi.star(episode.id, !episode.is_starred);
      setRefreshVersion(version => version + 1);
    } catch (error) {
      setActionNotice({ message: error.message || t("ui.couldNotSaveYourFavorite"), error: true });
    }
  };

  const handleFeedViewed = useCallback(async (feedId, latestEpisodeId) => {
    const owner = currentUserIdRef.current;
    try {
      const { data } = await feedsApi.recordView(feedId, latestEpisodeId);
      if (currentUserIdRef.current !== owner) return;
      feedList.update(feedId, { has_unseen_updates: data.has_unseen_updates });
      setSelectedFeed(previous => previous?.id === feedId ? { ...previous, has_unseen_updates: data.has_unseen_updates } : previous);
    } catch (error) {
      if (currentUserIdRef.current === owner) setActionNotice({ message: error.message || t('reading.saveFailed'), error: true });
    }
  }, [feedList.update, t]);

  // 订阅源收藏处理（乐观更新）
  const handleStarFeed = async (feed) => {
    const newFavorite = !feed.is_favorite;

    // 乐观更新：立即更新 feeds 状态
    feedList.update(feed.id, { is_favorite: newFavorite });

    // 更新 selectedFeed（如果当前选中的是这个feed）
    if (selectedFeed && selectedFeed.id === feed.id) {
      setSelectedFeed(prev => ({...prev, is_favorite: newFavorite}));
    }

    try {
      await feedsApi.favorite(feed.id, newFavorite);
    } catch (err) {
      console.error('Favorite failed:', err);
      // 失败时回滚
      feedList.update(feed.id, { is_favorite: !newFavorite });
      if (selectedFeed && selectedFeed.id === feed.id) {
        setSelectedFeed(prev => ({...prev, is_favorite: !newFavorite}));
      }
    }
  };

  // 播放控制函数
  const handlePlay = (episode, startSeconds) => {
    setPlaybackNotice(null);
    if (currentPlaying?.id === episode.id) {
      if (Number.isFinite(startSeconds) && startSeconds >= 0) {
        pendingPlaybackRef.current = { episodeId: episode.id, position: startSeconds };
        setIsPlaying(true);
        if (audioRef.current?.readyState >= 1) {
          audioRef.current.currentTime = startSeconds;
          pendingPlaybackRef.current = null;
          audioRef.current.play().catch(handlePlaybackRejected);
        }
        return;
      }
      // 如果是同一个episode，切换播放/暂停
      handlePlayPause(!isPlaying);
    } else {
      // 切换episode前保存当前播放位置
      if (currentPlaying && audioRef.current) {
        savePlayPosition(currentPlaying.id, audioRef.current.currentTime);
      }
      // 重置位置记录
      const position = getPlaybackPosition(episode, startSeconds);
      lastSavedPositionRef.current = position;
      pendingPlaybackRef.current = { episodeId: episode.id, position };
      // 播放新的episode
      setCurrentPlaying({
        ...episode,
        playable_audio_url: getPlayableAudioUrl(episode)
      });
      setIsPlaying(true);
    }
  };

  const handlePlaybackRejected = (error) => {
    if (error.name === 'AbortError') return;
    setIsPlaying(false);
    setPlaybackNotice({ message: t("ui.playbackDidNotStartUseThePlayer") });
  };

  const handleAudioReady = () => {
    const pending = pendingPlaybackRef.current;
    if (pending && pending.episodeId === currentPlaying?.id) {
      audioRef.current.currentTime = pending.position;
      pendingPlaybackRef.current = null;
    }
    if (isPlaying) audioRef.current.play().catch(handlePlaybackRejected);
  };

  const startReportPlayback = (episode, startSeconds) => {
    if (getPlayableAudioUrl(episode)) {
      handlePlay(episode, startSeconds);
      return;
    }
    const url = getExternalPlaybackUrl(episode, startSeconds);
    if (url) window.open(url, '_blank', 'noopener,noreferrer');
    setPlaybackNotice({ message: url ? t("ui.listenOnTheOriginalPlatformTheLink") : t("ui.thisEpisodeHasNoPlayableAudioYet"), url });
  };
  reportPlaybackRef.current = startReportPlayback;

  const handleReportListen = async (card) => {
    const episode = await openEpisode(card.episode_id);
    if (episode) startReportPlayback(episode, card.start);
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
      const position = pendingPlaybackRef.current?.position ?? audioRef.current?.currentTime;
      setPlaybackNotice({ message: t("ui.audioIsUnavailableHereListenOnThe"), url: getExternalPlaybackUrl(currentPlaying, position) });
      return;
    }

    pendingPlaybackRef.current = {
      episodeId: currentPlaying.id,
      position: pendingPlaybackRef.current?.position ?? audioRef.current.currentTime
    };
    setCurrentPlaying(prev => prev ? {
      ...prev,
      playable_audio_url: prev.audio_url,
      local_audio_failed: true
    } : prev);

  };

  if (authLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-black text-zinc-100">
        <div className="text-center">
          <RefreshCw className="animate-spin mx-auto mb-4 text-indigo-500" size={32} />
          <p className="text-zinc-400">{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return <AuthView onAuthenticated={handleAuthenticated} />;
  }

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
    <TasksProvider key={currentUser.id} pollIntervalMs={taskPollSeconds * 1000} onTaskComplete={handleTaskComplete} onTaskProgress={handleTaskProgress} queuedTask={queuedTask}>
    <div className="app-shell flex bg-black text-zinc-100 font-sans selection:bg-indigo-500/30 overflow-hidden" style={{ '--player-height': currentPlaying ? 'var(--player-size)' : '0px' }}>
      <Sidebar
        open={mobileSidebarOpen}
        onClose={() => setMobileSidebarOpen(false)}
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
        feedList={feedList}
        hasPlayer={!!currentPlaying}
        currentView={view}
        viewMode={viewMode}
        onViewModeChange={handleViewModeChange}
        briefingState={briefingState}
        onBriefingNavigate={handleBriefingNavigate}
      />

      {mobileSidebarOpen && (
        <div className="fixed inset-0 bg-black/60 z-30 md:hidden" onClick={() => setMobileSidebarOpen(false)} />
      )}

      <div className="app-main flex-1 flex flex-col min-w-0 bg-black relative">
        <MobileHeader mode={viewMode} onOpenMenu={() => setMobileSidebarOpen(true)} onOpenTasks={() => setTaskOpenRequest(value => value + 1)} />
        <div className="absolute top-0 left-0 w-full h-96 bg-indigo-900/10 pointer-events-none blur-3xl rounded-full translate-y-[-50%]"></div>

        <div className="absolute top-4 right-8 z-20 hidden md:block">
          <LanguageSwitcher />
        </div>

        <div className="app-page-content">
        {/* AI简报模式 */}
        {view.startsWith('briefing') ? (
          <BriefingReportsView
            key={currentUser.id}
            currentUser={currentUser}
            feeds={feeds}
            onOpenEpisode={openEpisode}
            onListen={handleReportListen}
            onOpenMenu={() => setMobileSidebarOpen(true)}
            hasPlayer={!!currentPlaying}
            section={view === 'briefingSettings' ? 'settings' : view === 'briefingSaved' ? 'saved' : 'reports'}
            navigation={briefingNavigation}
            onNavigationStateChange={handleBriefingStateChange}
            onSectionChange={handleBriefingNavigate}
          />
        ) : view === 'list' ? (
          <div className="flex-1 overflow-y-auto custom-scrollbar z-10">
            <div className="px-4 md:px-8 py-6 border-b border-zinc-800 bg-zinc-900/20">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <button
                    onClick={() => setMobileSidebarOpen(true)}
                    className="md:hidden shrink-0 rounded-lg border border-zinc-800 bg-zinc-900/60 p-2 text-zinc-300 hover:text-white"
                    aria-label={t('ui.openMenu')}
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
                  </button>
                  <div className="min-w-0">
                  <h2 className="text-2xl md:text-3xl font-bold text-white truncate">
                    {t('sidebar.subscriptions')}
                  </h2>
                  <p className="text-zinc-500 text-sm mt-1">
                    {feedList.pagination.total} {t('feed.subscriptions')}
                  </p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={() => loadData()}
                    aria-label={t("ui.refreshPageData")}
                    className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-xl text-sm font-medium transition-colors"
                  >
                    <RefreshCw size={16} />
                  </button>
                </div>
              </div>
            </div>

            <ViewToolbar
              count={`${feedList.pagination.total} ${t('feed.subscriptions')}`}
              description={t('viewToolbar.subscriptionsDescription')}
              viewMode={episodeViewMode}
              onViewModeChange={setEpisodeViewMode}
            />

            <div className={`p-4 md:p-8 grid ${episodeViewMode === 'list' ? 'grid-cols-1 gap-3' : 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4'} ${currentPlaying ? 'pb-24' : ''}`}>
              {feeds.map(feed => (
                <FeedCard key={feed.id} feed={feed} onClick={handleFeedClick} onRefresh={handleRefreshFeed} viewMode={episodeViewMode} />
              ))}
            </div>
            <ListPagination list={feedList} />
          </div>
        ) : view === 'feedDetail' ? (
          <FeedDetailView
            feed={selectedFeed}
            refreshVersion={refreshVersion}
            onBack={() => navigateToView('list')}
            onRefresh={handleRefreshFeed}
            canAutoRefresh={['user', 'admin'].includes(currentUser.role)}
            onEpisodeClick={handleEpisodeClick}
            onPlay={handlePlay}
            onStar={handleStar}
            onViewed={handleFeedViewed}
            viewMode={episodeViewMode}
            onViewModeChange={setEpisodeViewMode}
          />
        ) : view === 'favorites' ? (
          <FavoritesView
            refreshVersion={refreshVersion}
            feeds={feeds}
            onEpisodeClick={handleEpisodeClick}
            onPlay={handlePlay}
            onStar={handleStar}
            viewMode={episodeViewMode}
            onViewModeChange={setEpisodeViewMode}
          />
        ) : view === 'workspace' ? (
          <WorkspaceView
            refreshVersion={refreshVersion}
            feeds={feeds}
            onEpisodeClick={handleEpisodeClick}
            onPlay={handlePlay}
            onStar={handleStar}
            viewMode={episodeViewMode}
            onViewModeChange={setEpisodeViewMode}
          />
        ) : view === 'recent' ? (
          <RecentUpdatesView
            key={currentUser.id}
            refreshVersion={refreshVersion}
            feeds={feeds}
            onEpisodeClick={handleEpisodeClick}
            onPlay={handlePlay}
            onStar={handleStar}
            viewMode={episodeViewMode}
            onViewModeChange={setEpisodeViewMode}
          />
        ) : view === 'settings' ? (
          <SettingsView
            onBack={returnFromSettings}
            initialTab={settingsTab}
            currentUser={currentUser}
            onLogout={handleLogout}
          />
        ) : (
          <EpisodeDetailView
            key={`${selectedEpisode?.id}:${episodeOpenVersion}`}
            episode={selectedEpisode}
            activeTab={episodeTab}
            onTabChange={setEpisodeTab}
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
      </div>

      {/* 隐藏的audio元素 */}
      <audio
        ref={audioRef}
        src={currentPlaying?.playable_audio_url || currentPlaying?.audio_url}
        preload="metadata"
        onLoadedMetadata={handleAudioReady}
        onError={handleAudioError}
      />

      {actionNotice && (
        <div role={actionNotice.error ? 'alert' : 'status'} className={`app-notice fixed ${currentPlaying ? 'bottom-24' : 'bottom-4'} left-4 md:left-72 right-4 z-50 rounded-xl border ${actionNotice.error ? 'border-red-800 text-red-300' : 'border-zinc-700'} bg-zinc-900 px-4 py-3 text-sm flex items-center gap-3 shadow-xl`}>
          <span className="flex-1">{localizeUiMessage(actionNotice.message, t)}</span>
          <button onClick={() => setActionNotice(null)} aria-label={t("ui.dismissActionNotice")} className="text-zinc-400">{t("ui.close")}</button>
        </div>
      )}

      {playbackNotice && (
        <div role="status" className={`app-notice fixed ${currentPlaying ? 'bottom-24' : 'bottom-4'} left-4 md:left-72 right-4 z-50 rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm flex items-center gap-3 shadow-xl`}>
          <span className="flex-1">{playbackNotice.message}</span>
          {playbackNotice.url && <a href={playbackNotice.url} target="_blank" rel="noopener noreferrer" className="text-indigo-300 shrink-0">{t("ui.openOriginalPlatform")}</a>}
          <button onClick={() => setPlaybackNotice(null)} aria-label={t("ui.dismissPlaybackNotice")} className="text-zinc-400">{t("ui.close")}</button>
        </div>
      )}

      <PlayerBar
        episode={currentPlaying}
        isPlaying={isPlaying}
        onPlayPause={handlePlayPause}
        onSeek={handleSeek}
        audioRef={audioRef}
      />

      {/* 任务进度面板 */}
      <TaskPanel
        onRetrySubscription={retrySubscription}
        openRequest={taskOpenRequest}
        onNavigate={({ type, id, tab, ...context }) => {
          if (type === 'episode') openEpisode(id, { tab });
          if (type === 'feed') openFeed(id);
          if (type === 'briefing') handleBriefingNavigate('reports', context);
        }}
        historyWindowMinutes={taskHistoryWindowMinutes}
        defaultOpen={taskPanelDefaultOpen}
      />
    </div>
    </TasksProvider>
  );
}
