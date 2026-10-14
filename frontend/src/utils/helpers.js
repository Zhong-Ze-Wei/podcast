// -*- coding: utf-8 -*-
/**
 * HTML实体解码函数
 */
export const decodeHtmlEntities = (text) => {
  if (!text) return '';
  const doc = new DOMParser().parseFromString(text, 'text/html');
  return doc.documentElement.textContent;
};

// 旧 YouTube 订阅把内部频道 ID 存成默认简介；显示时使用原始订阅地址里的 @handle。
export const getFeedDescription = (feed) => {
  const description = decodeHtmlEntities(feed.description);
  const defaultYouTubeDescription = `YouTube 频道订阅 (${feed.channel_ref})`;
  if (feed.type !== 'youtube' || (description && description !== defaultYouTubeDescription)) return description;
  const handle = feed.rss_url?.match(/youtube\.com\/(@[^/?#]+)/i)?.[1];
  return `YouTube · ${handle || feed.title}`;
};

export const AI_ANALYSIS_ENABLED = ['1', 'true', 'yes', 'on'].includes(
  String(import.meta.env.VITE_AI_ANALYSIS_ENABLED || '').toLowerCase()
);
