// -*- coding: utf-8 -*-
import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Mic2, Sparkles, Download, Languages, AlertCircle } from 'lucide-react';
import { tasksApi } from '../../services/api';

/**
 * TaskProgress - 统一的任务进度组件
 *
 * 用于显示异步任务（转录、摘要、下载、翻译）的实时进度
 * 自动轮询后端获取真实进度，显示已运行时间和最后更新时间
 */
const TaskProgress = ({
  taskType,      // 'transcribe' | 'summarize' | 'download' | 'translate'
  episodeId,     // episode ID
  onComplete,    // 任务完成回调
  onError,       // 任务失败回调
  className = ''
}) => {
  const { t } = useTranslation();
  const [task, setTask] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(Date.now());
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // 任务类型配置
  const taskConfig = {
    transcribe: {
      icon: Mic2,
      label: t('detail.transcribingStatus') || 'Transcribing',
      color: 'purple'
    },
    summarize: {
      icon: Sparkles,
      label: t('detail.summarizingStatus') || 'Generating summary',
      color: 'indigo'
    },
    download: {
      icon: Download,
      label: t('detail.downloading') || 'Downloading',
      color: 'blue'
    },
    translate: {
      icon: Languages,
      label: t('detail.translating') || 'Translating',
      color: 'green'
    }
  };

  const config = taskConfig[taskType] || taskConfig.transcribe;
  const Icon = config.icon;

  // 轮询任务状态
  const fetchTaskStatus = useCallback(async () => {
    if (!episodeId) return;

    try {
      const response = await tasksApi.list({
        episode_id: episodeId,
        type: taskType,  // 后端参数名是 'type'
        per_page: 1
      });

      const tasks = response.data?.data || response.data || [];
      const activeTask = tasks.find(t =>
        t.status === 'pending' || t.status === 'processing'
      ) || tasks[0];

      if (activeTask) {
        setTask(activeTask);
        setLastUpdate(Date.now());

        // 计算已运行时间
        if (activeTask.started_at || activeTask.created_at) {
          const startTime = new Date(activeTask.started_at || activeTask.created_at).getTime();
          setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
        }

        // 任务完成或失败
        if (activeTask.status === 'completed') {
          onComplete?.();
        } else if (activeTask.status === 'failed') {
          onError?.(activeTask.error_message);
        }
      }
    } catch (err) {
      console.error('Failed to fetch task status:', err);
    }
  }, [episodeId, taskType, onComplete, onError]);

  // 轮询
  useEffect(() => {
    fetchTaskStatus();
    const interval = setInterval(fetchTaskStatus, 2000);
    return () => clearInterval(interval);
  }, [fetchTaskStatus]);

  // 更新已运行时间
  useEffect(() => {
    const interval = setInterval(() => {
      if (task?.started_at || task?.created_at) {
        const startTime = new Date(task.started_at || task.created_at).getTime();
        setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [task]);

  // 格式化时间
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${String(secs).padStart(2, '0')}`;
  };

  // 计算"最后更新"显示
  const getLastUpdateText = () => {
    const seconds = Math.floor((Date.now() - lastUpdate) / 1000);
    if (seconds < 5) return t('tasks.justNow') || 'just now';
    if (seconds < 60) return `${seconds}${t('tasks.secondsAgo') || 's ago'}`;
    return `${Math.floor(seconds / 60)}${t('tasks.minutesAgo') || 'm ago'}`;
  };

  const progress = task?.progress || 0;
  const isStale = Date.now() - lastUpdate > 30000; // 30秒无更新视为可能卡住

  // 颜色映射
  const colorClasses = {
    purple: {
      bg: 'bg-purple-500',
      bgLight: 'bg-purple-900/30',
      text: 'text-purple-400',
      border: 'border-purple-500/30'
    },
    indigo: {
      bg: 'bg-indigo-500',
      bgLight: 'bg-indigo-900/30',
      text: 'text-indigo-400',
      border: 'border-indigo-500/30'
    },
    blue: {
      bg: 'bg-blue-500',
      bgLight: 'bg-blue-900/30',
      text: 'text-blue-400',
      border: 'border-blue-500/30'
    },
    green: {
      bg: 'bg-green-500',
      bgLight: 'bg-green-900/30',
      text: 'text-green-400',
      border: 'border-green-500/30'
    }
  };

  const colors = colorClasses[config.color];

  return (
    <div className={`w-full max-w-sm ${className}`}>
      {/* 标题行 */}
      <div className="flex items-center gap-2 mb-3">
        <div className={`animate-spin ${colors.text}`}>
          <Icon size={20} />
        </div>
        <span className={`font-medium ${colors.text}`}>{config.label}</span>
      </div>

      {/* 进度条 */}
      <div className="w-full bg-zinc-800 rounded-full h-2 overflow-hidden mb-2">
        <div
          className={`h-full ${colors.bg} transition-all duration-500 ease-out`}
          style={{ width: `${Math.max(progress, 5)}%` }}
        />
      </div>

      {/* 信息行 */}
      <div className="flex items-center justify-between text-xs text-zinc-500">
        <span>{progress}%</span>
        <div className="flex items-center gap-3">
          <span>{t('tasks.elapsed') || 'Elapsed'}: {formatTime(elapsedSeconds)}</span>
          <span className={isStale ? 'text-yellow-500' : ''}>
            {t('tasks.lastUpdate') || 'Updated'}: {getLastUpdateText()}
          </span>
        </div>
      </div>

      {/* 卡住警告 */}
      {isStale && (
        <div className="flex items-center gap-2 mt-2 text-yellow-500 text-xs">
          <AlertCircle size={14} />
          <span>{t('tasks.maybeStuck') || 'Task may be stuck, please check backend logs'}</span>
        </div>
      )}

      {/* 错误信息 */}
      {task?.status === 'failed' && task?.error_message && (
        <div className="flex items-center gap-2 mt-2 text-red-400 text-xs bg-red-900/20 rounded-lg px-3 py-2">
          <AlertCircle size={14} />
          <span>{task.error_message}</span>
        </div>
      )}
    </div>
  );
};

export default TaskProgress;
