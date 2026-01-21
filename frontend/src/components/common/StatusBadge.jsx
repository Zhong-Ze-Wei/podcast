// -*- coding: utf-8 -*-
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Clock, Download, Mic2, FileText, Sparkles, CheckCircle2, AlertCircle } from 'lucide-react';

/**
 * StatusBadge - 状态徽章组件
 *
 * 根据节目状态显示对应的徽章样式和图标
 */
const StatusBadge = ({ status, hasTranscript, hasSummary }) => {
  const { t } = useTranslation();

  // 根据实际内容状态修正显示
  let displayStatus = status;

  // 如果有摘要，显示summarized
  if (hasSummary) {
    displayStatus = 'summarized';
  }
  // 如果有转录但没有摘要，显示transcribed
  else if (hasTranscript) {
    displayStatus = 'transcribed';
  }
  // 如果status是transcribed但没有实际转录，显示downloaded
  else if (status === 'transcribed' && !hasTranscript) {
    displayStatus = 'downloaded';
  }
  // 如果status是summarized但没有实际摘要，显示transcribed或downloaded
  else if (status === 'summarized' && !hasSummary) {
    displayStatus = hasTranscript ? 'transcribed' : 'downloaded';
  }

  const styles = {
    new: 'bg-zinc-800 text-zinc-400 border-zinc-700',
    downloaded: 'bg-blue-900/30 text-blue-400 border-blue-800',
    downloading: 'bg-blue-900/30 text-blue-400 border-blue-800 animate-pulse',
    transcribing: 'bg-purple-900/30 text-purple-400 border-purple-800 animate-pulse',
    transcribed: 'bg-green-900/30 text-green-400 border-green-800',
    summarizing: 'bg-amber-900/30 text-amber-400 border-amber-800 animate-pulse',
    summarized: 'bg-indigo-900/30 text-indigo-400 border-indigo-800',
    error: 'bg-red-900/30 text-red-400 border-red-800',
  };

  const icons = {
    new: <Clock size={12} />,
    downloaded: <Download size={12} />,
    downloading: <Download size={12} />,
    transcribing: <Mic2 size={12} />,
    transcribed: <FileText size={12} />,
    summarizing: <Sparkles size={12} />,
    summarized: <CheckCircle2 size={12} />,
    error: <AlertCircle size={12} />,
  };

  const label = displayStatus ? t(`status.${displayStatus}`) : t('status.new');

  return (
    <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${styles[displayStatus] || styles.new}`}>
      {icons[displayStatus]}
      <span>{label}</span>
    </div>
  );
};

export default StatusBadge;
