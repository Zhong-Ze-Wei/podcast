// 字幕定位优先于个人上次收听位置，0 秒也是有效的指定位置。
export function getPlaybackPosition(episode, startSeconds) {
  if (Number.isFinite(startSeconds) && startSeconds >= 0) return startSeconds;
  return episode.play_position || 0;
}

export function getExternalPlaybackUrl(episode, startSeconds) {
  const link = episode.link || (episode.guid?.startsWith('youtube:')
    ? `https://www.youtube.com/watch?v=${episode.guid.slice(8)}`
    : episode.guid?.startsWith('bilibili:')
      ? `https://www.bilibili.com/video/${episode.guid.slice(9)}`
      : episode.guid);
  if (!/^https?:\/\//i.test(link || '')) return '';
  const url = new URL(link);
  if (Number.isFinite(startSeconds) && startSeconds >= 0) {
    if (url.hostname === 'youtu.be' || /(^|\.)youtube\.com$/.test(url.hostname)) {
      url.searchParams.set('t', `${Math.floor(startSeconds)}s`);
    } else if (/(^|\.)bilibili\.com$/.test(url.hostname)) {
      url.searchParams.set('t', String(Math.floor(startSeconds)));
    }
  }
  return url.toString();
}
