// -*- coding: utf-8 -*-
/**
 * API Service
 *
 * 与后端通信的服务层
 */
import axios from 'axios';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json'
  }
});

const TOKEN_KEY = 'podcast_auth_token';

export const getAuthToken = () => localStorage.getItem(TOKEN_KEY);

export const setAuthToken = (token) => {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
};

api.interceptors.request.use(config => {
  const token = getAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器
api.interceptors.response.use(
  response => response.data,
  error => {
    const status = error.response?.status;
    const data = error.response?.data || {};
    const url = error.config?.url || '';

    // 404是预期情况（资源尚未创建），使用普通日志
    if (status === 404) {
      // 根据URL判断是什么资源
      let resourceType = 'Resource';
      if (url.includes('/transcripts/')) {
        resourceType = 'Transcript';
      } else if (url.includes('/summaries/')) {
        resourceType = 'Summary';
      }
      console.info(`${resourceType} not yet available (will be created when generated)`);
    } else if (status === 401) {
      setAuthToken(null);
    } else {
      console.error('API Error:', data.message || data);
    }
    return Promise.reject(data);
  }
);

// Feeds API
export const feedsApi = {
  list: (params = {}) => api.get('/feeds', { params }),
  get: (id) => api.get(`/feeds/${id}`),
  create: (data) => api.post('/feeds', data),
  update: (id, data) => api.put(`/feeds/${id}`, data),
  delete: (id) => api.delete(`/feeds/${id}`),
  refresh: (id) => api.post(`/feeds/${id}/refresh`),
  favorite: (id, favorite) => api.post(`/feeds/${id}/favorite`, { favorite }),
  getEpisodes: (id, params = {}) => api.get(`/feeds/${id}/episodes`, { params })
};

// Auth API
export const briefingLabApi = {
  snapshot: () => api.get('/briefing-lab'),
  run: (options) => api.post('/briefing-lab/run', options),
  task: (id) => api.get(`/briefing-lab/tasks/${id}`),
  source: (id) => api.get(`/briefing-lab/sources/${id}`)
};

export const briefingReportsApi = {
  modes: (params = {}) => api.get('/briefing-reports/modes', { params }),
  generateModes: (options) => api.post('/briefing-reports/modes/generate', options),
  preferences: () => api.get('/briefing-reports/preferences'),
  savePreferences: (options) => api.put('/briefing-reports/preferences', options),
  source: (sourceId) => api.get(`/briefing-reports/sources/${sourceId}`),
  edition: () => api.get('/briefing-reports/edition'),
  generateEdition: (options) => api.post('/briefing-reports/edition/generate', options),
  reading: (sourceId) => api.get(`/briefing-reports/reading/${sourceId}`),
  generateReading: (sourceId) => api.post(`/briefing-reports/reading/${sourceId}/generate`),
  snapshot: () => api.get('/briefing-reports'),
  generate: (options) => api.post('/briefing-reports/generate', options),
  task: (id) => api.get(`/briefing-reports/tasks/${id}`),
  html: (id, pages, style = 'legacy') => api.get(`/briefing-reports/reports/${id}/html`, {
    params: { pages, style }, responseType: 'text'
  }),
  pdf: (id, pages, style = 'legacy') => api.get(`/briefing-reports/reports/${id}/pdf`, {
    params: { pages, style }, responseType: 'blob'
  })
};

export const authApi = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  me: () => api.get('/auth/me')
};

// Admin API
export const adminApi = {
  users: () => api.get('/admin/users'),
  updateUser: (id, data) => api.patch(`/admin/users/${id}`, data),
  tasks: () => api.get('/admin/tasks'),
  health: () => api.get('/admin/health')
};

// Episodes API
export const episodesApi = {
  list: (params = {}) => api.get('/episodes', { params }),
  listTranscribed: () => api.get('/episodes', { params: { status: 'downloading,downloaded,transcribing,transcribed,summarizing,summarized', per_page: 1000 } }),
  get: (id) => api.get(`/episodes/${id}`),
  update: (id, data) => api.put(`/episodes/${id}`, data),
  star: (id, starred) => api.post(`/episodes/${id}/star`, { starred }),
  download: (id) => api.post(`/episodes/${id}/download`),
  // <audio> 标签带不了 Authorization 头，流地址经 query 参数携带令牌
  getStreamUrl: (id) => `${API_BASE}/episodes/${id}/stream?token=${getAuthToken()}`
};

// Transcripts API
export const transcriptsApi = {
  transcribeVideo: (episodeId) => api.post(`/transcripts/${episodeId}/fetch-video-audio`),
  get: (episodeId) => api.get(`/transcripts/${episodeId}`),
  create: (episodeId, options = {}) => api.post(`/transcripts/${episodeId}`, options),
  delete: (episodeId) => api.delete(`/transcripts/${episodeId}`),
  fetch: (episodeId) => api.post(`/transcripts/${episodeId}/fetch`),
  checkExternal: (episodeId) => api.get(`/transcripts/${episodeId}/check-external`)
};

// Summaries API
export const summariesApi = {
  get: (episodeId, params = {}) => api.get(`/summaries/${episodeId}`, { params }),
  create: (episodeId, options = {}) => api.post(`/summaries/${episodeId}`, options)
};

// Prompt Templates API
export const promptTemplatesApi = {
  list: (includeSystem = true) =>
    api.get('/prompt-templates', { params: { include_system: includeSystem } }),
  get: (idOrName) => api.get(`/prompt-templates/${idOrName}`),
  update: (id, data) => api.put(`/prompt-templates/${id}`, data),
  duplicate: (id, newName, newDisplayName) =>
    api.post(`/prompt-templates/${id}/duplicate`, { name: newName, display_name: newDisplayName }),
  delete: (id) => api.delete(`/prompt-templates/${id}`),
  init: () => api.post('/prompt-templates/init')
};

// Tasks API
export const tasksApi = {
  list: (params = {}) => api.get('/tasks', { params }),
  get: (id) => api.get(`/tasks/${id}`),
  cancel: (id) => api.post(`/tasks/${id}/cancel`)
};

// Settings API
export const settingsApi = {
  getLlmConfigs: () => api.get('/settings/llm'),
  saveLlmConfigs: (data) => api.put('/settings/llm', data),
  testLlmConnection: (config) => api.post('/settings/llm/test', config),
  fetchProviderModels: (providerId) => api.post('/settings/llm/fetch-models', { provider_id: providerId }),
  getAiAnalysis: () => api.get('/settings/ai-analysis'),
  getBilibiliStatus: () => api.get('/settings/bilibili-status'),
  setAiAnalysis: (enabled) => api.put('/settings/ai-analysis', { enabled }),
};

// Insights API (AI Briefing) —— strategy: summary | transcript | metadata；days: 时间窗口(1-30)
export const insightsApi = {
  getBriefing: (strategy, days) => api.get('/insights/briefing', {
    params: { ...(strategy && { strategy }), ...(days && { days }) },
  }),
  regenerateBriefing: (strategy, days) => api.post('/insights/briefing', null, {
    params: { ...(strategy && { strategy }), ...(days && { days }) },
  }),
  windowCount: (days) => api.get('/insights/briefing/count', { params: { days } }),
  exportPdf: async (strategy, days) => {
    // 经 axios 携带登录令牌取 PDF blob 再触发保存（<a> 直链不带 Authorization 会被 401 拒绝）
    const resp = await api.get('/insights/briefing/export', {
      responseType: 'blob',
      params: { ...(strategy && { strategy }), ...(days && { days }) },
    });
    const blob = resp instanceof Blob ? resp : new Blob([resp], { type: 'application/pdf' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const tags = [strategy && strategy !== 'summary' ? strategy : '', days && Number(days) !== 7 ? `${days}d` : ''].filter(Boolean);
    link.href = url;
    link.download = `podcast-briefing${tags.length ? '-' + tags.join('-') : ''}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
};

export default api;
