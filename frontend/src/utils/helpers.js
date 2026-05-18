// -*- coding: utf-8 -*-
/**
 * HTML实体解码函数
 */
export const decodeHtmlEntities = (text) => {
  if (!text) return '';
  const doc = new DOMParser().parseFromString(text, 'text/html');
  return doc.documentElement.textContent;
};

export const AI_ANALYSIS_ENABLED = ['1', 'true', 'yes', 'on'].includes(
  String(import.meta.env.VITE_AI_ANALYSIS_ENABLED || '').toLowerCase()
);
