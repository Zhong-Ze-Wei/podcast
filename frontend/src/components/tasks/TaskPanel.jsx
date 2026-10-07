// -*- coding: utf-8 -*-
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { localizeFeedProgress } from '../../utils/feedSyncProgress';
import {
  X, Download, Mic2, Sparkles, RefreshCw, CheckCircle2,
  AlertCircle, Loader2, Activity, Clock3, Grip, ChevronRight
} from 'lucide-react';
import { tasksApi } from '../../services/api';
import { subscriptionProgress } from '../../utils/subscriptionTask';
import { briefingTaskLabel, briefingTaskNavigation } from '../../utils/briefingTask';

const TASK_PANEL_SIZE_KEY = 'podcast_task_panel_size';
const DEFAULT_PANEL_SIZE = { width: 352, height: 480 };
const MIN_PANEL_SIZE = { width: 320, height: 360 };

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function readPanelSize() {
  try {
    const saved = JSON.parse(localStorage.getItem(TASK_PANEL_SIZE_KEY) || 'null');
    if (!saved) return DEFAULT_PANEL_SIZE;
    return {
      width: clamp(Number(saved.width) || DEFAULT_PANEL_SIZE.width, MIN_PANEL_SIZE.width, 720),
      height: clamp(Number(saved.height) || DEFAULT_PANEL_SIZE.height, MIN_PANEL_SIZE.height, 760)
    };
  } catch {
    return DEFAULT_PANEL_SIZE;
  }
}

const TaskPanel = ({
  onRetrySubscription,
  queuedTask,
  onTaskComplete,
  onTaskProgress,
  onTasksChange,
  onNavigate,
  pollIntervalMs = 3000,
  historyWindowMinutes = 60,
  defaultOpen = false
}) => {
  const { t, i18n } = useTranslation();
  const [activeTasks, setActiveTasks] = useState([]);
  const [historyTasks, setHistoryTasks] = useState([]);
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [activeTab, setActiveTab] = useState('active');
  const [dismissedTaskIds, setDismissedTaskIds] = useState(() => new Set());
  const [panelSize, setPanelSize] = useState(readPanelSize);
  const panelSizeRef = useRef(panelSize);
  const notifiedTaskIdsRef = useRef(new Set());
  const previousProgress = useRef({});
  const userClosedDuringActiveRef = useRef(false);
  const previousActiveCountRef = useRef(0);
  const resizeStateRef = useRef(null);

  useEffect(() => {
    if (!queuedTask) return;
    setActiveTasks(tasks => [...tasks.filter(task => task.id !== queuedTask.id), queuedTask]);
    setIsOpen(true);
    setActiveTab('active');
  }, [queuedTask]);

  const visibleHistoryTasks = historyTasks.filter(task => !dismissedTaskIds.has(task.id));

  const fetchTasks = useCallback(async () => {
    try {
      const [activeResponse, historyResponse] = await Promise.all([
        tasksApi.list({ status: 'pending,processing', per_page: 50 }),
        tasksApi.list({ status: 'completed,failed', per_page: 50 })
      ]);

      const nextActiveTasks = activeResponse.data || [];
      const historyCutoff = Date.now() - historyWindowMinutes * 60 * 1000;
      const nextHistoryTasks = (historyResponse.data || []).filter(task => {
        const completedAt = task.completed_at ? new Date(task.completed_at).getTime() : 0;
        return completedAt && completedAt > historyCutoff;
      });

      const changed = nextActiveTasks.filter(task => task.type === 'fetch_transcripts' && task.progress > 0 && task.progress !== previousProgress.current[task.id]);
      previousProgress.current = Object.fromEntries(nextActiveTasks.map(task => [task.id, task.progress]));
      onTasksChange?.(nextActiveTasks);
      if (changed.length) onTaskProgress?.(changed);
      setActiveTasks(nextActiveTasks);
      setHistoryTasks(nextHistoryTasks);

      const terminalTasks = nextHistoryTasks.filter(task =>
        task.id && !notifiedTaskIdsRef.current.has(task.id)
      );
      if (terminalTasks.length > 0 && onTaskComplete) {
        terminalTasks.forEach(task => notifiedTaskIdsRef.current.add(task.id));
        onTaskComplete(terminalTasks);
      }

      if (nextActiveTasks.length === 0) {
        userClosedDuringActiveRef.current = false;
      }
      if (
        nextActiveTasks.length > 0 &&
        previousActiveCountRef.current === 0 &&
        !userClosedDuringActiveRef.current
      ) {
        setIsOpen(true);
        setActiveTab('active');
      }
      previousActiveCountRef.current = nextActiveTasks.length;
    } catch (err) {
      console.error('Failed to fetch tasks:', err);
    }
  }, [historyWindowMinutes, onTaskComplete, onTaskProgress, onTasksChange]);

  useEffect(() => {
    fetchTasks();
    const interval = setInterval(fetchTasks, pollIntervalMs);
    return () => clearInterval(interval);
  }, [fetchTasks, pollIntervalMs]);

  useEffect(() => {
    if (defaultOpen) setIsOpen(true);
  }, [defaultOpen]);

  const closePanel = () => {
    if (activeTasks.length > 0) {
      userClosedDuringActiveRef.current = true;
    }
    setIsOpen(false);
  };

  useEffect(() => {
    const handlePointerMove = (event) => {
      const state = resizeStateRef.current;
      if (!state) return;

      const maxWidth = Math.max(MIN_PANEL_SIZE.width, window.innerWidth - 40);
      const maxHeight = Math.max(MIN_PANEL_SIZE.height, window.innerHeight - 180);
      const nextSize = {
        width: clamp(state.width + state.x - event.clientX, MIN_PANEL_SIZE.width, maxWidth),
        height: clamp(state.height + state.y - event.clientY, MIN_PANEL_SIZE.height, maxHeight)
      };
      panelSizeRef.current = nextSize;
      setPanelSize(nextSize);
    };

    const handlePointerUp = () => {
      if (!resizeStateRef.current) return;
      resizeStateRef.current = null;
      localStorage.setItem(TASK_PANEL_SIZE_KEY, JSON.stringify(panelSizeRef.current));
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, []);

  const handleResizeStart = (event) => {
    event.preventDefault();
    resizeStateRef.current = {
      x: event.clientX,
      y: event.clientY,
      width: panelSize.width,
      height: panelSize.height
    };
    document.body.style.cursor = 'nwse-resize';
    document.body.style.userSelect = 'none';
  };

  const handleCancel = async (taskId) => {
    try {
      await tasksApi.cancel(taskId);
      fetchTasks();
    } catch (err) {
      console.error('Failed to cancel task:', err);
    }
  };

  const handleDismiss = (taskId) => {
    setDismissedTaskIds(prev => {
      const next = new Set(prev);
      next.add(taskId);
      return next;
    });
  };

  const handleClearHistory = () => {
    setDismissedTaskIds(prev => {
      const next = new Set(prev);
      historyTasks.forEach(task => {
        if (task.id) next.add(task.id);
      });
      return next;
    });
  };

  const getTaskTargetLabel = (task) => {
    const periodLabel = briefingTaskLabel(task, i18n.language);
    if (periodLabel) return periodLabel;
    if (task.episode_title) return task.episode_title;
    if (task.feed_title) return task.feed_title;
    if (task.target_exists === false) return t('tasks.targetDeleted');
    if (task.episode_id) return t('tasks.unknownEpisode');
    if (task.feed_id) return t('tasks.unknownFeed');
    return '';
  };

  const getTaskMetaLabel = (task) => {
    const parts = [];
    if (task.feed_title && task.episode_title) parts.push(task.feed_title);
    if (task.episode_status) parts.push(t(`status.${task.episode_status}`, task.episode_status));
    return parts.join(' · ');
  };

  const canOpenTask = (task) => Boolean(onNavigate && (briefingTaskNavigation(task) || (task.target_id && task.target_type && task.target_exists !== false)));

  const handleOpenTask = (task) => {
    if (!canOpenTask(task)) return;
    const briefing = briefingTaskNavigation(task);
    onNavigate(briefing ? { type: 'briefing', ...briefing, task } : { type: task.target_type, id: task.target_id, task });
    setIsOpen(false);
  };

  const handleTaskKeyDown = (event, task) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    handleOpenTask(task);
  };

  const getTaskIcon = (type) => {
    switch (type) {
      case 'download': return <Download size={16} />;
      case 'transcribe': return <Mic2 size={16} />;
      case 'summarize': return <Sparkles size={16} />;
      case 'briefing-report': return <Sparkles size={16} />;
      case 'refresh': return <RefreshCw size={16} />;
      case 'subscribe': return <RefreshCw size={16} />;
      case 'fetch_transcripts': return <Mic2 size={16} />;
      default: return <Loader2 size={16} />;
    }
  };

  const getStatusStyle = (status) => {
    switch (status) {
      case 'pending': return 'text-zinc-400';
      case 'processing': return 'text-sky-400';
      case 'completed': return 'text-emerald-400';
      case 'failed': return 'text-red-400';
      default: return 'text-zinc-400';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'pending': return <Loader2 size={14} className="animate-pulse" />;
      case 'processing': return <Loader2 size={14} className="animate-spin" />;
      case 'completed': return <CheckCircle2 size={14} />;
      case 'failed': return <AlertCircle size={14} />;
      default: return null;
    }
  };

  const formatRelativeTime = (value) => {
    if (!value) return '';
    const diffSeconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
    if (diffSeconds < 5) return t('tasks.justNow');
    if (diffSeconds < 60) return t('tasks.time.secondsAgo', { count: diffSeconds });
    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) return t('tasks.time.minutesAgo', { count: diffMinutes });
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return t('tasks.time.hoursAgo', { count: diffHours });
    return t('tasks.time.daysAgo', { count: Math.floor(diffHours / 24) });
  };

  const renderTask = (task) => {
    const isActive = task.status === 'pending' || task.status === 'processing';
    const errorMessage = ['refresh', 'fetch_transcripts', 'subscribe'].includes(task.type)
      ? t('common.fetchUnavailable')
      : task.error_message;
    const targetLabel = getTaskTargetLabel(task);
    const metaLabel = getTaskMetaLabel(task);
    const isOpenable = canOpenTask(task);
    return (
      <div
        key={task.id}
        role={isOpenable ? 'button' : undefined}
        tabIndex={isOpenable ? 0 : undefined}
        onClick={() => handleOpenTask(task)}
        onKeyDown={(event) => handleTaskKeyDown(event, task)}
        title={isOpenable ? t('tasks.openTarget') : undefined}
        className={`group flex items-start gap-3 px-4 py-3 border-b border-zinc-800/80 last:border-b-0 transition-colors ${isOpenable ? 'cursor-pointer hover:bg-zinc-800/50 focus:outline-none focus:bg-zinc-800/50' : 'hover:bg-zinc-800/30'}`}
      >
        <div className={`mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md bg-zinc-950 border border-zinc-800 ${getStatusStyle(task.status)}`}>
          {getTaskIcon(task.type)}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm text-zinc-200 truncate">
              {t(`tasks.types.${task.type}`)}
            </span>
            <span className={`flex items-center gap-1 text-xs ${getStatusStyle(task.status)}`}>
              {getStatusIcon(task.status)}
              {t(`tasks.status.${task.status}`)}
            </span>
          </div>

          {targetLabel && (
            <div className="mt-1 min-w-0">
              <p className={`truncate text-xs ${task.target_exists === false ? 'text-zinc-600' : 'text-zinc-300'}`}>
                {targetLabel}
              </p>
              {metaLabel && (
                <p className="mt-0.5 truncate text-[11px] text-zinc-500">
                  {metaLabel}
                </p>
              )}
            </div>
          )}

          {isActive ? (
            <div className="mt-2">
              {task.progress_message && (
                <p className="mb-1 truncate text-[11px] text-sky-300">{localizeFeedProgress(subscriptionProgress(task.progress_message, t), t)}</p>
              )}
              <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-300 ${task.status === 'processing' ? 'bg-sky-500' : 'bg-zinc-600'}`}
                  style={{ width: `${Math.max(task.progress || 0, task.status === 'processing' ? 8 : 0)}%` }}
                />
              </div>
            </div>
          ) : (
            <div className="mt-1 flex items-center gap-1 text-xs text-zinc-500">
              <Clock3 size={12} />
              <span>{formatRelativeTime(task.completed_at)}</span>
            </div>
          )}

          {task.status === 'failed' && task.error_message && (
            <p className="text-xs text-red-400 mt-1 truncate" title={errorMessage}>
              {errorMessage}
            </p>
          )}
          {task.type === 'subscribe' && task.status === 'failed' && task.report_context?.url && <button type="button" onClick={event => { event.stopPropagation(); onRetrySubscription(task.report_context.url); setActiveTab('active'); }} className="mt-2 rounded-md bg-sky-500/10 px-3 py-1.5 text-xs text-sky-300 hover:bg-sky-500/20">{t('tasks.retrySubscription')}</button>}
        </div>

        <div className="flex-shrink-0">
          {task.status === 'pending' && (
            <button
              onClick={(event) => { event.stopPropagation(); handleCancel(task.id); }}
              className="p-1 text-zinc-500 hover:text-red-400 transition-colors"
              title={t('tasks.cancel')}
            >
              <X size={14} />
            </button>
          )}
          {(task.status === 'completed' || task.status === 'failed') && (
            <button
              onClick={(event) => { event.stopPropagation(); handleDismiss(task.id); }}
              className="p-1 text-zinc-600 opacity-0 group-hover:opacity-100 hover:text-zinc-300 transition-all"
              title={t('tasks.dismiss')}
            >
              <X size={14} />
            </button>
          )}
          {isOpenable && (
            <ChevronRight size={14} className="mt-2 text-zinc-600 opacity-0 transition-opacity group-hover:opacity-100" />
          )}
        </div>
      </div>
    );
  };

  const visibleTasks = activeTab === 'active' ? activeTasks : visibleHistoryTasks;
  const hasActiveTasks = activeTasks.length > 0;
  const hasFailures = visibleHistoryTasks.some(task => task.status === 'failed');

  return (
    <>
      {isOpen && (
        <div
          className="fixed bottom-40 right-5 z-50 flex max-h-[calc(100vh-12rem)] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl shadow-black/50"
          style={{ width: `${panelSize.width}px`, height: `${panelSize.height}px` }}
        >
          <button
            onPointerDown={handleResizeStart}
            className="absolute left-1 top-1 z-10 flex h-6 w-6 cursor-nwse-resize items-center justify-center rounded-md text-zinc-600 hover:bg-zinc-800 hover:text-zinc-300"
            title={t('tasks.resizePanel')}
          >
            <Grip size={13} />
          </button>
          <div className="flex items-center justify-between px-4 py-3 bg-zinc-950/70 border-b border-zinc-800">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-700 bg-zinc-900 text-sky-400">
                <Activity size={16} className={hasActiveTasks ? 'animate-pulse' : ''} />
              </div>
              <div>
                <div className="text-sm font-semibold text-zinc-100">{t('tasks.title')}</div>
                <div className="text-xs text-zinc-500">
                  {hasActiveTasks
                    ? t('tasks.activeCount', { count: activeTasks.length })
                    : t('tasks.recentCount', { count: visibleHistoryTasks.length })}
                </div>
              </div>
            </div>
            <button
              onClick={closePanel}
              className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
              title={t('tasks.dismiss')}
            >
              <X size={16} />
            </button>
          </div>

          <div className="flex items-center justify-between gap-2 px-3 py-2 bg-zinc-900 border-b border-zinc-800">
            <div className="grid grid-cols-2 gap-1 rounded-lg bg-zinc-950 p-1">
              <button
                onClick={() => setActiveTab('active')}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${activeTab === 'active' ? 'bg-sky-600 text-white' : 'text-zinc-500 hover:text-zinc-200'}`}
              >
                {t('tasks.tabs.active')} {activeTasks.length > 0 ? activeTasks.length : ''}
              </button>
              <button
                onClick={() => setActiveTab('history')}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${activeTab === 'history' ? 'bg-sky-600 text-white' : 'text-zinc-500 hover:text-zinc-200'}`}
              >
                {t('tasks.tabs.history')} {visibleHistoryTasks.length > 0 ? visibleHistoryTasks.length : ''}
              </button>
            </div>

            {activeTab === 'history' && visibleHistoryTasks.length > 0 && (
              <button
                onClick={handleClearHistory}
                className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                {t('tasks.clearCompleted')}
              </button>
            )}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto custom-scrollbar">
            {visibleTasks.length > 0 ? (
              visibleTasks.map(renderTask)
            ) : (
              <div className="flex flex-col items-center justify-center px-6 py-10 text-center">
                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950 text-zinc-600">
                  {activeTab === 'active' ? <Loader2 size={18} /> : <Clock3 size={18} />}
                </div>
                <p className="text-sm font-medium text-zinc-300">
                  {activeTab === 'active' ? t('tasks.emptyActive') : t('tasks.emptyHistory')}
                </p>
                <p className="mt-1 text-xs text-zinc-500">
                  {activeTab === 'active'
                    ? t('tasks.emptyActiveHint')
                    : t('tasks.emptyHistoryHint')}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      <button
        onClick={() => setIsOpen(prev => !prev)}
        className="fixed bottom-24 right-5 z-50 h-14 w-14 rounded-full border border-zinc-700 bg-zinc-900 text-zinc-100 shadow-2xl shadow-black/50 transition-transform hover:scale-105 hover:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/60"
        title={isOpen ? t('tasks.closePanel') : t('tasks.openPanel')}
      >
        <span
          className={`absolute inset-0 rounded-full opacity-80 ${hasActiveTasks ? 'animate-spin' : ''}`}
          style={{
            background: hasActiveTasks
              ? 'conic-gradient(from 120deg, rgba(14,165,233,0), rgba(14,165,233,0.95), rgba(16,185,129,0.85), rgba(14,165,233,0))'
              : hasFailures
                ? 'conic-gradient(from 120deg, rgba(239,68,68,0), rgba(239,68,68,0.9), rgba(239,68,68,0))'
                : 'conic-gradient(from 120deg, rgba(63,63,70,0), rgba(113,113,122,0.8), rgba(63,63,70,0))'
          }}
        />
        <span className="absolute inset-[3px] rounded-full bg-zinc-950" />
        <span className="relative flex h-full w-full items-center justify-center">
          {hasActiveTasks ? <Loader2 size={22} className="animate-spin text-sky-400" /> : <Activity size={22} className="text-zinc-300" />}
        </span>
        {hasActiveTasks && (
          <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-sky-500 px-1.5 py-0.5 text-[11px] font-bold text-white">
            {activeTasks.length}
          </span>
        )}
        {!hasActiveTasks && visibleHistoryTasks.length > 0 && (
          <span className="absolute -right-1 -top-1 h-3 w-3 rounded-full border-2 border-zinc-950 bg-emerald-400" />
        )}
      </button>
    </>
  );
};

export default TaskPanel;
