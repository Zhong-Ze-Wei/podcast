// -*- coding: utf-8 -*-
import React, { useState, useEffect } from 'react';
import { Play, Pause, SkipBack, SkipForward, Volume2, Maximize2, Mic2 } from 'lucide-react';

/**
 * PlayerBar - 底部播放器组件
 *
 * 功能：
 * - 显示当前播放的节目信息
 * - 播放/暂停控制
 * - 快进/快退（-15s/+30s）
 * - 进度条（可点击跳转）
 * - 音量控制
 */
const PlayerBar = ({ episode, isPlaying, onPlayPause, onSeek, audioRef }) => {
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(0.7);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handleTimeUpdate = () => setCurrentTime(audio.currentTime);
    const handleDurationChange = () => setDuration(audio.duration || 0);
    const handleEnded = () => onPlayPause(false);

    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('durationchange', handleDurationChange);
    audio.addEventListener('ended', handleEnded);

    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('durationchange', handleDurationChange);
      audio.removeEventListener('ended', handleEnded);
    };
  }, [audioRef, onPlayPause]);

  const formatTime = (seconds) => {
    if (!seconds || isNaN(seconds)) return '0:00';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
      return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const handleProgressClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const percent = (e.clientX - rect.left) / rect.width;
    const newTime = percent * duration;
    onSeek(newTime);
  };

  const handleVolumeChange = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const percent = (e.clientX - rect.left) / rect.width;
    const newVolume = Math.max(0, Math.min(1, percent));
    setVolume(newVolume);
    if (audioRef.current) {
      audioRef.current.volume = newVolume;
    }
  };

  const handleSkip = (seconds) => {
    if (audioRef.current) {
      onSeek(Math.max(0, Math.min(duration, currentTime + seconds)));
    }
  };

  if (!episode) return null;

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="h-20 bg-zinc-950/80 backdrop-blur-xl border-t border-zinc-800 flex items-center px-6 fixed bottom-0 w-full z-50">
      <div className="flex items-center gap-4 w-1/3">
        <div className="w-12 h-12 bg-zinc-800 rounded-lg overflow-hidden relative group">
          <div className="absolute inset-0 bg-black/20 group-hover:bg-black/0 transition-colors"></div>
          <div className="w-full h-full bg-gradient-to-br from-indigo-900 to-zinc-900 flex items-center justify-center text-zinc-500">
            <Mic2 size={20} />
          </div>
        </div>
        <div className="overflow-hidden">
          <h4 className="text-sm font-medium text-white truncate">{episode.title}</h4>
          <p className="text-xs text-zinc-400 truncate">{episode.feed_title || episode.feed?.title}</p>
        </div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center gap-2">
        <div className="flex items-center gap-6">
          <button
            onClick={() => handleSkip(-15)}
            className="text-zinc-400 hover:text-white transition-colors"
            title="-15s"
          >
            <SkipBack size={20} />
          </button>
          <button
            onClick={() => onPlayPause(!isPlaying)}
            className="w-10 h-10 bg-white rounded-full flex items-center justify-center text-black hover:scale-105 transition-transform shadow-lg shadow-white/10"
          >
            {isPlaying ? (
              <Pause size={20} fill="currentColor" stroke="none" />
            ) : (
              <Play size={20} fill="currentColor" stroke="none" className="ml-0.5" />
            )}
          </button>
          <button
            onClick={() => handleSkip(30)}
            className="text-zinc-400 hover:text-white transition-colors"
            title="+30s"
          >
            <SkipForward size={20} />
          </button>
        </div>
        <div className="w-full max-w-md flex items-center gap-3 text-xs text-zinc-500">
          <span className="w-10 text-right">{formatTime(currentTime)}</span>
          <div
            className="flex-1 h-1 bg-zinc-800 rounded-full overflow-hidden cursor-pointer group"
            onClick={handleProgressClick}
          >
            <div
              className="h-full bg-indigo-500 rounded-full transition-all group-hover:bg-indigo-400"
              style={{ width: `${progress}%` }}
            ></div>
          </div>
          <span className="w-10">{formatTime(duration)}</span>
        </div>
      </div>

      <div className="w-1/3 flex items-center justify-end gap-4">
        <Volume2 size={18} className="text-zinc-400" />
        <div
          className="w-24 h-1 bg-zinc-800 rounded-full overflow-hidden cursor-pointer"
          onClick={handleVolumeChange}
        >
          <div
            className="h-full bg-zinc-500 hover:bg-zinc-400 transition-colors"
            style={{ width: `${volume * 100}%` }}
          ></div>
        </div>
        <button className="text-zinc-400 hover:text-white"><Maximize2 size={18} /></button>
      </div>
    </div>
  );
};

export default PlayerBar;
