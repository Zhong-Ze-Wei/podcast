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
  star: (id, starred) => api.post(`/feeds/${id}/star`, { starred }),
  favorite: (id, favorite) => api.post(`/feeds/${id}/favorite`, { favorite }),
  getEpisodes: (id, params = {}) => api.get(`/feeds/${id}/episodes`, { params })
};

// Episodes API
export const episodesApi = {
  list: (params = {}) => api.get('/episodes', { params }),
  listTranscribed: () => api.get('/episodes', { params: { status: 'transcribing,transcribed,summarizing,summarized', per_page: 1000 } }),
  listSummarized: () => api.get('/episodes', { params: { status: 'summarizing,summarized', per_page: 1000 } }),
  get: (id) => api.get(`/episodes/${id}`),
  update: (id, data) => api.put(`/episodes/${id}`, data),
  star: (id, starred) => api.post(`/episodes/${id}/star`, { starred }),
  markRead: (id, isRead) => api.post(`/episodes/${id}/read`, { is_read: isRead }),
  download: (id) => api.post(`/episodes/${id}/download`)
};

// Transcripts API
export const transcriptsApi = {
  get: (episodeId) => api.get(`/transcripts/${episodeId}`),
  create: (episodeId) => api.post(`/transcripts/${episodeId}`),
  delete: (episodeId) => api.delete(`/transcripts/${episodeId}`),
  fetch: (episodeId) => api.post(`/transcripts/${episodeId}/fetch`),
  checkExternal: (episodeId) => api.get(`/transcripts/${episodeId}/check-external`)
};

// Summaries API
export const summariesApi = {
  get: (episodeId, params = {}) => {
    // params can include: template_name or summary_type
    return api.get(`/summaries/${episodeId}`, { params });
  },
  // New template-based API
  create: (episodeId, options = {}) => {
    // options: { template_name, enabled_blocks, params, force } or legacy { summary_type, force }
    return api.post(`/summaries/${episodeId}`, options);
  },
  translate: (episodeId, options = {}) =>
    api.post(`/summaries/${episodeId}/translate`, options),
  delete: (episodeId, params = {}) => {
    // params: { template_name } or { summary_type }
    return api.delete(`/summaries/${episodeId}`, { params });
  },
  getTypes: () => api.get('/summaries/types'),
  getTemplates: () => api.get('/summaries/templates')
};

// Prompt Templates API
export const promptTemplatesApi = {
  list: (includeSystem = true) =>
    api.get('/prompt-templates', { params: { include_system: includeSystem } }),
  get: (idOrName) => api.get(`/prompt-templates/${idOrName}`),
  create: (data) => api.post('/prompt-templates', data),
  update: (id, data) => api.put(`/prompt-templates/${id}`, data),
  duplicate: (id, newName, newDisplayName) =>
    api.post(`/prompt-templates/${id}/duplicate`, { name: newName, display_name: newDisplayName }),
  delete: (id) => api.delete(`/prompt-templates/${id}`),
  getBlocks: (idOrName) => api.get(`/prompt-templates/${idOrName}/blocks`),
  getParameters: (idOrName) => api.get(`/prompt-templates/${idOrName}/parameters`),
  init: () => api.post('/prompt-templates/init')
};

// Tasks API
export const tasksApi = {
  list: (params = {}) => api.get('/tasks', { params }),
  get: (id) => api.get(`/tasks/${id}`),
  cancel: (id) => api.post(`/tasks/${id}/cancel`)
};

// Stats API
export const statsApi = {
  get: () => api.get('/stats')
};

// Settings API
export const settingsApi = {
  getLlmConfigs: () => api.get('/settings/llm'),
  saveLlmConfigs: (data) => api.put('/settings/llm', data),
  setActiveLlm: (index) => api.put('/settings/llm/active', { index }),
  testLlmConnection: (config) => api.post('/settings/llm/test', config)
};

export default api;
