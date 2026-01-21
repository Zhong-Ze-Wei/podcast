// -*- coding: utf-8 -*-
/**
 * HTML实体解码函数
 */
export const decodeHtmlEntities = (text) => {
  if (!text) return '';
  const doc = new DOMParser().parseFromString(text, 'text/html');
  return doc.documentElement.textContent;
};
