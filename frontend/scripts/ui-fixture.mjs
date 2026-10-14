// 使用：node scripts/ui-fixture.mjs。仅在 127.0.0.1:3007 提供测试数据，不连接生产后端。
import http from 'node:http';
import { readFile } from 'node:fs/promises';
const readingTheme = await readFile(new URL('../../backend/app/static/briefing-reading-theme.css', import.meta.url), 'utf8');
import { createServer } from 'vite';

const requests = [];
const feedViews = new Map();
const user = { id: 'fixture-user', username: 'fixture', email: 'fixture@example.test', role: 'admin' };
const feeds = Array.from({ length: 36 }, (_, i) => ({ id: `feed-${i + 1}`, title: `播客 ${i + 1}：人工智能与商业的长期观察`, author: '测试播客', description: '用于验证页面分页和长标题的真实长度示例。', rss_url: `https://example.test/feed-${i + 1}`, episode_count: 80, is_favorite: false }));
const episodes = Array.from({ length: 80 }, (_, i) => ({ id: `episode-${i + 1}`, feed_id: 'feed-1', feed_title: feeds[0].title, title: `第 ${i + 1} 期：机器人与 AI Native 产品的商业实践和长期变化`, description: '从产品设计、工程架构到商业模式的讨论。', published: new Date(Date.UTC(2026, 8, 30 - i)).toISOString(), duration: 10800, status: i % 4 === 0 ? 'transcribing' : 'transcribed', has_transcript: i % 4 !== 0, has_summary: i % 3 === 0, local_audio_url: i % 2 === 0 ? '/api/audio/sample.wav' : null, audio_url: '/api/audio/sample.wav', is_starred: i >= 70, artifacts: { local_audio: i % 2 === 0, transcript: i % 4 !== 0, summary: i % 3 === 0 }, actions: { download: { allowed: true }, transcribe: { allowed: true }, summarize: { allowed: true } }, transcription_providers: [{ id: 'official', available: false, reason_code: 'NO_TRANSCRIPT_URL' }, { id: 'local_whisper', available: true, download_required: i % 2 !== 0 }, { id: 'local_whisperx', available: false, reason_code: 'LOCAL_AI_NOT_INSTALLED' }, { id: 'assemblyai', available: false, reason_code: 'CLOUD_TRANSCRIPTION_DISABLED' }], active_tasks: [] }));
episodes[1].has_transcript = false; episodes[1].artifacts.transcript = false; episodes[1].has_summary = false; episodes[1].artifacts.summary = false; episodes[1].actions.summarize = { allowed: false, reason_code: 'TRANSCRIPT_NOT_FOUND' };
for (const episode of episodes) episode.published_at = episode.published;
const period = { type: 'week', start: '2026-09-21', end: '2026-09-27', label: '9月21日 — 9月27日', total_count: 10, transcript_count: 10, is_current: false };
const sources = episodes.slice(0, 10).map((item, i) => ({ id: `source-${i + 1}`, episode_id: item.id, title: item.title, feed: item.feed_title, transcript_ready: true }));
const modes = [{ id: 'core', name: '核心提要' }, { id: 'quotes', name: '原话精选' }, { id: 'connections', name: '共性与分歧' }, { id: 'concepts', name: '新词与方法' }, { id: 'resources', name: '提到的资料' }];
const reports = Object.fromEntries(modes.map(mode => [mode.id, { id: `report-${mode.id}`, mode: mode.id, title: mode.name, generated_at: '2026-09-28T00:05:00+08:00', period, sources, sections: [{ items: Array.from({ length: 16 }, (_, i) => ({ id: `item-${mode.id}-${i + 1}`, kind: mode.id === 'quotes' ? 'quote' : 'insight', source_id: sources[i % 10].id, episode_id: sources[i % 10].episode_id, title: `第 ${i + 1} 条：产品边界与可靠执行`, text: '用户关闭页面后业务任务仍应继续执行。架构需要明确职责，界面则突出当前阅读内容。'.repeat(3), quote: '用户关闭页面后，任务仍应继续执行。', feed: sources[i % 10].feed, source_title: sources[i % 10].title, start: i * 120, topic_tags: ['AI', '编程'], evidence: [] })) }] } ]));
let preferences = { interests: [{ label: 'AI', enabled: true }], auto_period: 'week', layout: 'paper' };
for (const report of Object.values(reports)) {
  for (const item of report.sections[0].items) {
    if (item.kind !== 'quote') item.evidence = [{ ...item, evidence: undefined }];
  }
  report.sections[0].items[0].title = 'AI 做科学要先把问题变成可打分任务';
  report.sections[0].items[0].text = 'ERA 把科学问题写成可优化评分的代码，由 AI 循环搜索候选；但评分始终依赖人的设定，人类创造力与严谨仍不可替代。';
  report.sections[0].items[1].title = '同一 AI 工具产出优劣取决于谁掌判断';
  report.sections[0].items[1].text = '工具的产出取决于谁用在工作流何处，以及谁负责判断与验证。';
}
const oldReport = { ...reports.core, id: 'report-old', title: '上周核心提要', period: { ...period, start: '2026-09-14', label: '9月14日 — 9月20日' } };
const oldItem = { ...reports.core.sections[0].items[0], id: 'old-saved-item', title: '跨周期收藏：上周的架构观点' };
const favorites = new Map([[oldItem.id, { item_id: oldItem.id, report_id: oldReport.id, item: oldItem, report: oldReport, created_at: '2026-09-21T00:00:00Z' }]]);
const tasks = [];
let taskCounter = 0;
const template = { id: 'learning', name: 'learning', display_name: '学习笔记', optional_blocks: [], parameters: {} };
const readings = new Map();
const sourceFor = id => {
  const source = sources.find(item => item.id === id);
  const episode = episodes.find(item => item.id === (source?.episode_id || id.replace(/^ep/, '')));
  return episode && { ...episode, id, episode_id: episode.id, feed: episode.feed_title, full_text: '用户关闭页面后，任务仍应继续执行。\n同一份分析可以用于单篇阅读，也可以用于周报和月报。\n兴趣变化只需要重新筛选，已经完成的全文解读可以继续使用。', segments: [] };
};
const analysisFor = source => {
  const quotes = source.full_text.split('\n').map((quote, index) => ({ id: `q-${index}`, source_id: source.id, episode_id: source.episode_id, feed: source.feed, source_title: source.title, quote, brief: ['任务连续性', '共享分析', '个性化筛选'][index], start: null, offset: source.full_text.indexOf(quote) }));
  return { generated_at: '2026-10-02T00:00:00Z', version: 1, analysis_key: 'fixture-shared-analysis', takeaway: '这期讨论分析结果如何长期保留：逐篇理解文稿，再按用户关心的问题组织周报、月报。', points: quotes.map((quote, index) => ({ title: quote.brief, meaning: ['处理任务独立于阅读页面，切换页面后仍可以回来查看进度。', '单篇分析保存后，周报和月报复用它，并各自补充跨节目联系。', '问题影响选材，不让同一篇因为周期或兴趣变化而重复分析。'][index], quote })), quotes, concepts: [{ title: '方法：先单篇，再汇总', text: '先保存每篇带原文依据的解读，再按时间范围组织材料。', ...quotes[1] }], resources: [] };
};
readings.set('episode-3', true);
const send = (res, data, status = 200) => { res.writeHead(status, { 'content-type': 'application/json; charset=utf-8' }); res.end(JSON.stringify({ success: status < 400, data, message: status >= 400 ? data.message : null })); };
const paginated = (res, data, url, meta) => {
  const page = Number(url.searchParams.get('page') || 1);
  const perPage = Number(url.searchParams.get('per_page') || 24);
  res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify({ success: true, data: data.slice((page - 1) * perPage, page * perPage), pagination: { page, per_page: perPage, total: data.length, has_next: page * perPage < data.length }, ...(meta ? { meta } : {}) }));
};
const latestEpisode = feedId => Math.max(0, ...episodes.filter(item => item.feed_id === feedId).map(item => Number(item.id.split('-')[1])));
const feedForUser = feed => ({ ...feed, has_unseen_updates: latestEpisode(feed.id) > (feedViews.get(`${user.id}:${feed.id}`) || 0), unread_count: episodes.filter(item => item.feed_id === feed.id && !item.is_read).length });
const body = async req => { let text = ''; for await (const chunk of req) text += chunk; return text ? JSON.parse(text) : {}; };
function episodeList(url, feedId) {
  let data = episodes.filter(item => !feedId || item.feed_id === feedId);
  for (const [param, field] of [['is_starred', 'is_starred'], ['is_read', 'is_read'], ['has_transcript', 'has_transcript'], ['has_summary', 'has_summary']]) if (url.searchParams.has(param)) data = data.filter(item => Boolean(item[field]) === (url.searchParams.get(param) === 'true'));
  if (url.searchParams.get('has_transcript_or_summary') === 'true') data = data.filter(item => item.has_transcript || item.has_summary);
  if (url.searchParams.has('days')) { const now = Date.now(); const cutoff = now - Number(url.searchParams.get('days')) * 86400000; data = data.filter(item => Date.parse(item.published) >= cutoff && Date.parse(item.published) <= now); }
  if (url.searchParams.get('has_local_audio') === 'true') data = data.filter(item => item.artifacts.local_audio);
  if (url.searchParams.get('processed') === 'true') data = data.filter(item => Object.values(item.artifacts).some(Boolean));
  const q = url.searchParams.get('q')?.toLowerCase();
  if (q) data = data.filter(item => `${item.title} ${item.description}`.toLowerCase().includes(q));
  if (url.searchParams.get('sort') === 'published_asc') data = [...data].reverse();
  if (url.searchParams.get('sort') === 'title_asc') data = [...data].sort((a, b) => a.title.localeCompare(b.title));
  return data;
}
function episodeForUser(item) {
  if (user.role !== 'viewer') return item;
  return { ...item, actions: Object.fromEntries(Object.keys(item.actions).map(action => [action, { allowed: false, reason_code: 'ROLE_DENIED' }])), transcription_providers: item.transcription_providers.map(provider => ({ ...provider, available: false, reason_code: 'ROLE_DENIED' })) };
}
async function api(req, res) {
  const url = new URL(req.url, 'http://127.0.0.1:3007');
  const path = url.pathname;
  const payload = req.method === 'GET' ? {} : await body(req);
  requests.push({ method: req.method, path, params: Object.fromEntries(url.searchParams), payload });
  if (path === '/api/audio/sample.wav') { const samples = 8000 * 30; const wav = Buffer.alloc(44 + samples * 2); wav.write('RIFF', 0); wav.writeUInt32LE(wav.length - 8, 4); wav.write('WAVEfmt ', 8); wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22); wav.writeUInt32LE(8000, 24); wav.writeUInt32LE(16000, 28); wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34); wav.write('data', 36); wav.writeUInt32LE(samples * 2, 40); res.writeHead(200, { 'content-type': 'audio/wav', 'content-length': wav.length }); return res.end(wav); }
  if (path === '/api/__fixture/capability') { const item = episodes.find(item => item.id === payload.id); item.actions.transcribe = { allowed: !payload.busy, reason_code: payload.busy ? 'TASK_IN_PROGRESS' : null }; item.actions.summarize = { allowed: !payload.busy && item.has_transcript, reason_code: payload.busy ? 'TASK_IN_PROGRESS' : item.has_transcript ? null : 'TRANSCRIPT_NOT_FOUND' }; return send(res, item); }
  if (path === '/api/__fixture/role') { user.role = payload.role; return send(res, user); }
  if (path === '/api/__fixture/new-episode') { const episode = { ...episodes[0], id: `episode-${episodes.length + 1}`, title: '补录旧节目也是新更新', feed_id: payload.feed_id || 'feed-1', published: '2020-01-01T00:00:00Z', published_at: '2020-01-01T00:00:00Z', is_read: false }; episodes.push(episode); return send(res, episode); }
  if (path === '/api/__fixture/complete-task') { const task = tasks.find(item => item.id === payload.id); task.status = payload.status || 'completed'; task.progress = 100; task.result = payload.result || {}; task.completed_at = new Date().toISOString(); if (task.status === 'completed' && task.report_context?.kind === 'reading') readings.set(sourceFor(task.report_context.source_id).episode_id, true); return send(res, task); }
  if (path === '/api/__fixture/requests') return send(res, requests);
  if (path === '/api/auth/me') return send(res, { user });
  if (path === '/api/feeds') return paginated(res, feeds.map(feedForUser), url);
  if (/^\/api\/feeds\/[^/]+\/episodes$/.test(path)) { const feedId = path.split('/')[3]; const latest = latestEpisode(feedId); return paginated(res, episodeList(url, feedId).map(episodeForUser), url, { latest_episode_id: latest ? `episode-${latest}` : null }); }
  if (/^\/api\/feeds\/[^/]+\/refresh$/.test(path)) { const id = `task-${++taskCounter}`; tasks.unshift({ id, type: 'refresh', feed_id: path.split('/')[3], feed_title: feeds[0].title, status: 'pending', can_cancel: true, progress: 0, created_at: new Date().toISOString() }); return send(res, { task_id: id, status: 'queued' }); }
  if (/^\/api\/feeds\/[^/]+\/view$/.test(path)) { const feedId = path.split('/')[3]; const key = `${user.id}:${feedId}`; feedViews.set(key, Math.max(feedViews.get(key) || 0, Number(payload.latest_episode_id.split('-')[1]))); return send(res, { feed_id: feedId, has_unseen_updates: feedForUser(feeds.find(item => item.id === feedId)).has_unseen_updates }); }
  if (/^\/api\/feeds\/[^/]+$/.test(path)) return send(res, feedForUser(feeds.find(item => item.id === path.split('/')[3])));
  if (path === '/api/episodes') return paginated(res, episodeList(url).map(episodeForUser), url);
  if (/^\/api\/episodes\/[^/]+\/star$/.test(path)) { const item = episodes.find(item => item.id === path.split('/')[3]); item.is_starred = payload.starred; return send(res, item); }
  if (/^\/api\/episodes\/[^/]+\/read$/.test(path)) { const item = episodes.find(item => item.id === path.split('/')[3]); item.is_read = payload.is_read; return send(res, { id: item.id, is_read: item.is_read, feed_id: item.feed_id, unread_count: episodes.filter(other => other.feed_id === item.feed_id && !other.is_read).length }); }
  if (/^\/api\/episodes\/[^/]+$/.test(path)) return send(res, episodeForUser(episodes.find(item => item.id === path.split('/')[3])));
  if (path === '/api/tasks') { const statuses = url.searchParams.get('status')?.split(','); return paginated(res, tasks.filter(task => (!statuses || statuses.includes(task.status)) && (!url.searchParams.get('type') || task.type === url.searchParams.get('type')) && (!url.searchParams.get('period_start') || task.report_period?.start === url.searchParams.get('period_start')) && (!url.searchParams.get('period_type') || task.report_period?.type === url.searchParams.get('period_type')) && (!url.searchParams.get('episode_id') || task.episode_id === url.searchParams.get('episode_id'))), url); }
  if (/^\/api\/tasks\/[^/]+\/cancel$/.test(path)) { const task = tasks.find(item => item.id === path.split('/')[3]); if (!task?.can_cancel) return send(res, { message: '运行中的任务当前无法停止' }, 409); task.status = 'cancelled'; task.can_cancel = false; task.completed_at = new Date().toISOString(); return send(res, task); }
  if (/^\/api\/tasks\/[^/]+$/.test(path)) return send(res, tasks.find(item => item.id === path.split('/')[3]));
  if (/^\/api\/transcripts\/[^/]+\/check-external$/.test(path)) return send(res, { has_external_transcript: false });
  if (/^\/api\/transcripts\/[^/]+$/.test(path)) { if (req.method === 'POST') { const id = `task-${++taskCounter}`; tasks.unshift({ id, type: 'transcribe', episode_id: path.split('/')[3], episode_title: episodes[0].title, status: 'processing', can_cancel: false, progress: 25, progress_message: '下载音频', created_at: new Date().toISOString() }); episodes.find(item => item.id === path.split('/')[3]).active_tasks = [{ task_id: id, task_type: 'transcribe', status: 'processing', progress: 25, progress_message: '下载音频' }]; return send(res, { task_id: id, status: 'queued' }); } return send(res, { message: '尚无文稿' }, 404); }
  if (path === '/api/prompt-templates') return send(res, { templates: [template] });
  if (path.startsWith('/api/prompt-templates/')) return send(res, template);
  if (path.startsWith('/api/summaries/')) return send(res, { message: '尚无摘要' }, 404);
  if (path === '/api/settings/ai-analysis') return send(res, { enabled: true });
  if (path === '/api/briefing-reports/modes/generate' || /^\/api\/briefing-reports\/reading\/[^/]+\/generate$/.test(path)) {
    const kind = path.includes('/reading/') ? 'reading' : 'modes';
    const source = kind === 'reading' ? sourceFor(path.split('/')[4]) : null;
    const id = `task-${++taskCounter}`;
    tasks.unshift({ id, type: 'briefing-report', status: 'processing', can_cancel: false, progress: 40,
      progress_message: '正在读取这一期完整文稿；已有分析将直接复用',
      report_period: { type: payload.period_type, start: payload.period_start },
      report_context: { kind, mode: payload.mode, source_id: source?.id, source_title: source?.title, feed_title: source?.feed },
      ...(source ? { episode_id: source.episode_id, episode_title: source.title, feed_title: source.feed, target_type: 'episode', target_id: source.episode_id, target_exists: true } : {}),
      created_at: new Date().toISOString() });
    return send(res, { task_id: id, status: 'queued' });
  }
  if (/^\/api\/briefing-reports\/reading\/[^/]+$/.test(path)) { const source = sourceFor(path.split('/')[4]); return source ? send(res, { source, reading: readings.has(source.episode_id) ? analysisFor(source) : null }) : send(res, { message: '文稿不存在' }, 404); }
  if (/^\/api\/briefing-reports\/sources\/[^/]+$/.test(path)) return send(res, sourceFor(path.split('/')[4]));
  if (path === '/api/briefing-reports/preferences') { if (req.method === 'PUT') preferences = { ...preferences, ...payload }; return send(res, preferences); }
  if (path === '/api/briefing-reports/modes') return send(res, { reports, modes, sources, period: { ...period, type: url.searchParams.get('period_type') || 'week', start: url.searchParams.get('period_start') || period.start }, periods: [period], preferences });
  if (path === '/api/briefing-reports/favorites/import') { const imported = []; const unresolved = []; for (const id of payload.ids || []) { const report = Object.values(reports).find(report => report.sections[0].items.some(item => item.id === id)); if (!report) unresolved.push(id); else { const item = report.sections[0].items.find(item => item.id === id); favorites.set(id, { item_id: id, report_id: report.id, item, report, created_at: new Date().toISOString() }); imported.push(id); } } return send(res, { imported, unresolved }); }
  if (path === '/api/briefing-reports/favorites') return paginated(res, [...favorites.values()].filter(item => (!url.searchParams.get('mode') || item.report.mode === url.searchParams.get('mode')) && (!url.searchParams.get('period_start') || item.report.period.start === url.searchParams.get('period_start')) && (!url.searchParams.get('period_type') || item.report.period.type === url.searchParams.get('period_type'))), url);
  if (path.startsWith('/api/briefing-reports/favorites/')) { const id = decodeURIComponent(path.split('/').at(-1)); if (req.method === 'DELETE') { favorites.delete(id); return send(res, { item_id: id, deleted: true }); } const report = Object.values(reports).find(report => report.id === payload.report_id); const item = report?.sections[0].items.find(item => item.id === id); if (!item) return send(res, { message: '条目不存在' }, 404); const favorite = { item_id: id, report_id: report.id, item, report, created_at: new Date().toISOString() }; favorites.set(id, favorite); return send(res, favorite); }
  if (path === '/api/briefing-reports/reading-theme.css') { res.writeHead(200, { 'content-type': 'text/css' }); return res.end(readingTheme); }
  if (path === '/api/admin/users') return send(res, [user]);
  if (path === '/api/admin/health') return send(res, { users: 1, feeds: feeds.length, episodes: episodes.length, tasks: tasks.length });
  if (path.startsWith('/api/admin/')) return send(res, {});
  return send(res, { message: `Fixture route unavailable: ${path}` }, 404);
}
const port = Number(process.env.UI_FIXTURE_PORT || 3007);
const vite = await createServer({ server: { middlewareMode: true, hmr: { port: port + 10000 } }, appType: 'spa' });
http.createServer((req, res) => req.url.startsWith('/api/') ? api(req, res).catch(error => send(res, { message: error.message }, 500)) : vite.middlewares(req, res)).listen(port, '127.0.0.1', () => process.stdout.write(`Frontend fixture: http://127.0.0.1:${port}\n`));
