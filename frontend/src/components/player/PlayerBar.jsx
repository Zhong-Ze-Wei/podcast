import { useTranslation } from 'react-i18next';
import React, { useState, useEffect } from 'react';
import { Play, Pause, SkipBack, SkipForward, Volume2, Mic2 } from 'lucide-react';

const formatTime = seconds => {
  const value = Number.isFinite(seconds) ? Math.floor(seconds) : 0;
  const h = Math.floor(value / 3600);
  const m = Math.floor(value % 3600 / 60);
  const s = value % 60;
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`;
};

// 手机使用两行播放器；原生 range 支持拖动、触屏与方向键调整。
export default function PlayerBar({ episode, isPlaying, onPlayPause, onSeek, audioRef }) {
  const { t } = useTranslation();
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(0.7);
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const time = () => setCurrentTime(audio.currentTime);
    const metadata = () => setDuration(Number.isFinite(audio.duration) ? audio.duration : episode?.duration || 0);
    const ended = () => onPlayPause(false);
    audio.addEventListener('timeupdate', time);
    audio.addEventListener('durationchange', metadata);
    audio.addEventListener('ended', ended);
    return () => { audio.removeEventListener('timeupdate', time); audio.removeEventListener('durationchange', metadata); audio.removeEventListener('ended', ended); };
  }, [audioRef, onPlayPause, episode?.duration]);
  useEffect(() => { setCurrentTime(0); setDuration(0); }, [episode?.id]);
  useEffect(() => { if (audioRef.current) audioRef.current.volume = volume; }, [audioRef, volume]);
  if (!episode) return null;
  const skip = seconds => onSeek(Math.max(0, Math.min(duration, currentTime + seconds)));
  return <section className="player-bar" aria-label={t("ui.audioPlayer")}>
    <div className="player-title"><div className="player-cover"><Mic2 size={20} /></div><div><h4>{episode.title}</h4><p>{episode.feed_title || episode.feed?.title}</p></div></div>
    <div className="player-controls">
      <button onClick={() => skip(-15)} aria-label={t("ui.back15Seconds")} disabled={!duration}><SkipBack size={20} /></button>
      <button onClick={() => onPlayPause(!isPlaying)} className="player-play" aria-label={isPlaying ? t("ui.pausePlayback") : t("ui.resumePlayback")}>{isPlaying ? <Pause size={20} fill="currentColor" stroke="none" /> : <Play size={20} fill="currentColor" stroke="none" />}</button>
      <button onClick={() => skip(30)} aria-label={t("ui.forward30Seconds")} disabled={!duration}><SkipForward size={20} /></button>
    </div>
    <div className="player-seek"><span>{formatTime(currentTime)}</span><input type="range" aria-label={t("ui.playbackPosition")} min="0" max={duration || 0} step="1" value={Math.min(currentTime, duration)} disabled={!duration} onChange={event => onSeek(Number(event.target.value))} /><span>{formatTime(duration)}</span></div>
    <label className="player-volume"><Volume2 size={18} aria-hidden="true" /><input type="range" aria-label={t("ui.volume")} min="0" max="1" step="0.05" value={volume} onChange={event => setVolume(Number(event.target.value))} /></label>
  </section>;
}
