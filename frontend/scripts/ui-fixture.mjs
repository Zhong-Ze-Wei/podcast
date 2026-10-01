// 使用：node scripts/ui-fixture.mjs。仅在 127.0.0.1:3007 提供测试数据，不连接生产后端。
import http from 'node:http';
import { createServer } from 'vite';

const requests = [];
const user = { id: 'fixture-user', username: 'fixture', email: 'fixture@example.test', role: 'admin' };
const feeds = Array.from({ length: 36 }, (_, i) => ({ id: `feed-${i + 1}`, title: `播客 ${i + 1}：人工智能与商业的长期观察`, author: '测试播客', description: '用于验证页面分页和长标题的真实长度示例。', rss_url: `https://example.test/feed-${i + 1}`, episode_count: 80, is_favorite: false }));
const episodes = Array.from({ length: 80 }, (_, i) => ({ id: `episode-${i + 1}`, feed_id: 'feed-1', feed_title: feeds[0].title, title: `第 ${i + 1} 期：机器人与 AI Native 产品的商业实践和长期变化`, description: '从产品设计、工程架构到商业模式的讨论。', published: new Date(Date.UTC(2026, 8, 30 - i)).toISOString(), duration: 10800, status: i % 4 === 0 ? 'transcribing' : 'transcribed', has_transcript: i % 4 !== 0, has_summary: i % 3 === 0, local_audio_url: i % 2 === 0 ? '/api/audio/sample.wav' : null, audio_url: '/api/audio/sample.wav', is_starred: i >= 70, artifacts: { local_audio: i % 2 === 0, transcript: i % 4 !== 0, summary: i % 3 === 0 }, actions: { download: { allowed: true }, transcribe: { allowed: true }, summarize: { allowed: true } }, transcription_providers: [{ id: 'official', available: false, reason_code: 'NO_OFFICIAL_TRANSCRIPT' }, { id: 'local_whisper', available: true, download_required: i % 2 !== 0 }, { id: 'local_whisperx', available: false, reason_code: 'LOCAL_RUNTIME_UNAVAILABLE' }, { id: 'assemblyai', available: false, reason_code: 'CLOUD_DISABLED' }], active_tasks: [] }));
const period = { type: 'week', start: '2026-09-21', end: '2026-09-27', label: '9月21日 — 9月27日', total_count: 10, transcript_count: 10, is_current: false };
const sources = episodes.slice(0, 10).map((item, i) => ({ id: `source-${i + 1}`, episode_id: item.id, title: item.title, feed: item.feed_title, transcript_ready: true }));
const modes = [{ id: 'core', name: '核心提要' }, { id: 'quotes', name: '原话精选' }, { id: 'connections', name: '共性与分歧' }, { id: 'concepts', name: '新词与方法' }, { id: 'resources', name: '提到的资料' }];
const reports = Object.fromEntries(modes.map(mode => [mode.id, { id: `report-${mode.id}`, mode: mode.id, title: mode.name, generated_at: '2026-09-28T00:05:00+08:00', period, sources, sections: [{ items: Array.from({ length: 16 }, (_, i) => ({ id: `item-${mode.id}-${i + 1}`, kind: mode.id === 'quotes' ? 'quote' : 'insight', source_id: sources[i % 10].id, episode_id: sources[i % 10].episode_id, title: `第 ${i + 1} 条：产品边界与可靠执行`, text: '用户关闭页面后业务任务仍应继续执行。架构需要明确职责，界面则突出当前阅读内容。'.repeat(3), quote: '用户关闭页面后，任务仍应继续执行。', feed: sources[i % 10].feed, source_title: sources[i % 10].title, start: i * 120, topic_tags: ['AI', '编程'], evidence: [] })) }] } ]));
let preferences = { interests: [{ label: 'AI', enabled: true }], auto_period: 'week', layout: 'paper' };
const favorites = new Map();
const tasks = [];
let taskCounter = 0;
const template = { id: 'learning', name: 'learning', display_name: '学习笔记', optional_blocks: [], parameters: {} };
const send = (res, data, status = 200) => { res.writeHead(status, { 'content-type': 'application/json; charset=utf-8' }); res.end(JSON.stringify({ success: status < 400, data, message: status >= 400 ? data.message : null })); };
const paginated = (res, data, url) => {
  const page = Number(url.searchParams.get('page') || 1);
  const perPage = Number(url.searchParams.get('per_page') || 24);
  res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify({ success: true, data: data.slice((page - 1) * perPage, page * perPage), pagination: { page, per_page: perPage, total: data.length, has_next: page * perPage < data.length } }));
};
const body = async req => { let text = ''; for await (const chunk of req) text += chunk; return text ? JSON.parse(text) : {}; };
function episodeList(url, feedId) {
  let data = episodes.filter(item => !feedId || item.feed_id === feedId);
  for (const [param, field] of [['is_starred', 'is_starred'], ['has_transcript', 'has_transcript'], ['has_summary', 'has_summary']]) if (url.searchParams.has(param)) data = data.filter(item => item[field] === (url.searchParams.get(param) === 'true'));
  if (url.searchParams.get('has_local_audio') === 'true') data = data.filter(item => item.artifacts.local_audio);
  if (url.searchParams.get('processed') === 'true') data = data.filter(item => Object.values(item.artifacts).some(Boolean));
  const q = url.searchParams.get('q')?.toLowerCase();
  if (q) data = data.filter(item => `${item.title} ${item.description}`.toLowerCase().includes(q));
  if (url.searchParams.get('sort') === 'published_asc') data = [...data].reverse();
  if (url.searchParams.get('sort') === 'title_asc') data = [...data].sort((a, b) => a.title.localeCompare(b.title));
  return data;
}
async function api(req, res) {
  const url = new URL(req.url, 'http://127.0.0.1:3007');
  const path = url.pathname;
  const payload = req.method === 'GET' ? {} : await body(req);
  requests.push({ method: req.method, path, params: Object.fromEntries(url.searchParams), payload });
  if (path === '/api/__fixture/requests') return send(res, requests);
  if (path === '/api/auth/me') return send(res, { user });
  if (path === '/api/feeds') return paginated(res, feeds, url);
  if (/^\/api\/feeds\/[^/]+\/episodes$/.test(path)) return paginated(res, episodeList(url, path.split('/')[3]), url);
  if (/^\/api\/feeds\/[^/]+\/refresh$/.test(path)) { const id = `task-${++taskCounter}`; tasks.unshift({ id, type: 'refresh', feed_id: path.split('/')[3], feed_title: feeds[0].title, status: 'pending', can_cancel: true, progress: 0, created_at: new Date().toISOString() }); return send(res, { task_id: id, status: 'queued' }); }
  if (/^\/api\/feeds\/[^/]+$/.test(path)) return send(res, feeds.find(item => item.id === path.split('/')[3]));
  if (path === '/api/episodes') return paginated(res, episodeList(url), url);
  if (/^\/api\/episodes\/[^/]+\/star$/.test(path)) { const item = episodes.find(item => item.id === path.split('/')[3]); item.is_starred = payload.starred; return send(res, item); }
  if (/^\/api\/episodes\/[^/]+$/.test(path)) return send(res, episodes.find(item => item.id === path.split('/')[3]));
  if (path === '/api/tasks') { const statuses = url.searchParams.get('status')?.split(','); return paginated(res, tasks.filter(task => (!statuses || statuses.includes(task.status)) && (!url.searchParams.get('episode_id') || task.episode_id === url.searchParams.get('episode_id'))), url); }
  if (/^\/api\/tasks\/[^/]+\/cancel$/.test(path)) { const task = tasks.find(item => item.id === path.split('/')[3]); if (!task?.can_cancel) return send(res, { message: '运行中的任务当前无法停止' }, 409); task.status = 'cancelled'; task.can_cancel = false; task.completed_at = new Date().toISOString(); return send(res, task); }
  if (/^\/api\/tasks\/[^/]+$/.test(path)) return send(res, tasks.find(item => item.id === path.split('/')[3]));
  if (/^\/api\/transcripts\/[^/]+\/check-external$/.test(path)) return send(res, { has_external_transcript: false });
  if (/^\/api\/transcripts\/[^/]+$/.test(path)) { if (req.method === 'POST') { const id = `task-${++taskCounter}`; tasks.unshift({ id, type: 'transcribe', episode_id: path.split('/')[3], episode_title: episodes[0].title, status: 'processing', can_cancel: false, progress: 25, progress_message: '下载音频', created_at: new Date().toISOString() }); return send(res, { task_id: id, status: 'queued' }); } return send(res, { message: '尚无文稿' }, 404); }
  if (path === '/api/prompt-templates') return send(res, { templates: [template] });
  if (path.startsWith('/api/prompt-templates/')) return send(res, template);
  if (path.startsWith('/api/summaries/')) return send(res, { message: '尚无摘要' }, 404);
  if (path === '/api/settings/ai-analysis') return send(res, { enabled: true });
  if (path === '/api/briefing-reports/preferences') { if (req.method === 'PUT') preferences = { ...preferences, ...payload }; return send(res, preferences); }
  if (path === '/api/briefing-reports/modes') return send(res, { reports, modes, sources, period: { ...period, type: url.searchParams.get('period_type') || 'week', start: url.searchParams.get('period_start') || period.start }, periods: [period], preferences });
  if (path === '/api/briefing-reports/favorites/import') { const imported = []; const unresolved = []; for (const id of payload.ids || []) { const report = Object.values(reports).find(report => report.sections[0].items.some(item => item.id === id)); if (!report) unresolved.push(id); else { const item = report.sections[0].items.find(item => item.id === id); favorites.set(id, { item_id: id, report_id: report.id, item, report, created_at: new Date().toISOString() }); imported.push(id); } } return send(res, { imported, unresolved }); }
  if (path === '/api/briefing-reports/favorites') return paginated(res, [...favorites.values()].filter(item => !url.searchParams.get('mode') || item.report.mode === url.searchParams.get('mode')), url);
  if (path.startsWith('/api/briefing-reports/favorites/')) { const id = decodeURIComponent(path.split('/').at(-1)); if (req.method === 'DELETE') { favorites.delete(id); return send(res, { item_id: id, deleted: true }); } const report = Object.values(reports).find(report => report.id === payload.report_id); const item = report?.sections[0].items.find(item => item.id === id); if (!item) return send(res, { message: '条目不存在' }, 404); const favorite = { item_id: id, report_id: report.id, item, report, created_at: new Date().toISOString() }; favorites.set(id, favorite); return send(res, favorite); }
  if (path === '/api/briefing-reports/reading-theme.css') { res.writeHead(200, { 'content-type': 'text/css' }); return res.end(''); }
  if (path.startsWith('/api/admin/')) return send(res, {});
  return send(res, { message: `Fixture route unavailable: ${path}` }, 404);
}
const vite = await createServer({ server: { middlewareMode: true }, appType: 'spa' });
http.createServer((req, res) => req.url.startsWith('/api/') ? api(req, res).catch(error => send(res, { message: error.message }, 500)) : vite.middlewares(req, res)).listen(3007, '127.0.0.1', () => process.stdout.write('Frontend fixture: http://127.0.0.1:3007\n'));
