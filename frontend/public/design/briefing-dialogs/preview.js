const variants = [
  { id: 'grid', number: '01', title: ['双列图文', 'The collection'], caption: ['整齐卡片 · 快速浏览', 'Aligned cards · quick scanning'], rationale: ['最接近现有习惯。封面、两行标题和操作区固定高度，适合周报和月报快速扫读。', 'A familiar two-column collection. Fixed cover, title and action areas keep short and long titles aligned.'], reference: 'https://mcp.21st.dev/%40felipemenezes098/components/content-04' },
  { id: 'date', number: '02', title: ['按日分组', 'The journal'], caption: ['日期分组 · 轻盈纸感', 'By date · a paper-like journal'], rationale: ['用发布日期组织卡片，先看最近，再往前翻。适合节目较多的月报，也能看清一周的更新节奏。', 'Cards grouped by publication date. Useful for a busy month and for following the rhythm of a week.'], reference: 'https://21st.dev/@isaiahbjork/components/animated-project-cards' },
  { id: 'detail', number: '03', title: ['卡片侧阅', 'The reading desk'], caption: ['左侧选片 · 右侧预览', 'Select on the left · read on the right'], rationale: ['点击卡片，右侧立即展示完整标题、简介和入口。适合逐篇比较，不需要反复打开、关闭弹窗。', 'Select a card to see its full title, description and links alongside the collection. Good for comparing episodes.'], reference: 'https://mcp.21st.dev/%40originui/components/dialog' },
  { id: 'stack', number: '04', title: ['叠放翻阅', 'The card deck'], caption: ['倾斜叠卡 · 拖动翻页', 'Tilted cards · drag to browse'], rationale: ['露出左右两张卡片，可以拖动、点击或用方向键翻阅。适合少量节目；几十期的月报，浏览效率会低一些。', 'Peek at adjacent cards and browse by dragging, clicking or using arrow keys. Best for a smaller weekly collection.'], reference: 'https://21st.dev/@kedhareswer/components/tilt-cascade-carousel' },
  { id: 'gallery', number: '05', title: ['封面画廊', 'The cover gallery'], caption: ['大幅封面 · 原位展开', 'Larger covers · expand in place'], rationale: ['封面更突出，点击卡片会在原位置展开简介。视觉识别更强，适合按节目寻找内容，空间占用稍多。', 'Larger artwork makes shows easy to recognize. Expand a card in place to read more, at the cost of some density.'], reference: 'https://21st.dev/@dhileepkumargm/components/3d-interactive-card-gallery' },
];

const translations = {
  zh: {
    preview: '交互预览', headline: '每一期，都值得被看见。', intro: '用你已有的节目，比较五种卡片弹窗。试试搜索、点开卡片，再选一个喜欢的。',
    week: '周报', month: '月报', fullscreen: '全屏体验', reopen: '重新打开弹窗', copy: '复制选择', choose: '选这个方案',
    footnote: '读取已保存的节目，不生成新分析。你选定后，再应用到周报和月报。', fullscreenHint: '按 Esc 返回方案选择', return: '返回选择',
    heading: '这个周期的节目', total: '总计', episodes: '期', transcript: '有文稿', analyzed: '已有解读', missing: '暂无文稿',
    all: '全部节目', withText: '有文稿', withAnalysis: '已解读', search: '搜索节目或订阅', allSources: '全部订阅',
    close: '关闭弹窗', open: '打开节目', reading: '查看解读', analyze: '单篇解读', description: '节目简介',
    noDescription: '这期暂无节目简介，可打开节目阅读文稿。', previewEpisode: '预览这期', back: '返回节目卡片',
    result: '已显示', clickHint: '点击卡片查看完整标题与简介', previous: '上一期', next: '下一期', dragHint: '左右拖动 · 点击侧卡 · 方向键翻阅',
    loading: '正在整理节目卡片', loadingNote: '读取已保存的节目与订阅封面。', failure: '暂时无法读取节目', failureNote: '请确认项目已启动，并在 PodMaster 登录后重试。',
    retry: '重新读取', login: '打开 PodMaster', empty: '没有匹配的节目', emptyNote: '换一个关键词，或清除筛选条件试试。', reset: '清除筛选',
    reference: '参考 21st', selected: '已选择方案', copied: '已复制', copyFailure: '请把方案编号告诉我', detailLabel: 'EPISODE / 节目预览',
    noDate: '日期未知', untitled: '未命名节目', chooseNotice: '已记住你的选择；正式弹窗还未替换。', noPeriod: '这个周期暂无节目',
  },
  en: {
    preview: 'INTERACTIVE PREVIEW', headline: 'Every episode deserves a closer look.', intro: 'Five card dialogs, using your saved episodes. Search, open a card and choose your favorite.',
    week: 'Weekly', month: 'Monthly', fullscreen: 'Full screen', reopen: 'Open the dialog again', copy: 'Copy choice', choose: 'Choose this design',
    footnote: 'Uses saved episodes without generating new analysis. Your choice will then be applied to weekly and monthly reports.', fullscreenHint: 'Press Esc to return to the designs', return: 'Back to designs',
    heading: 'Episodes in this period', total: 'Total', episodes: 'episodes', transcript: 'Transcript', analyzed: 'Analyzed', missing: 'No transcript',
    all: 'All episodes', withText: 'With transcript', withAnalysis: 'Analyzed', search: 'Search episodes or shows', allSources: 'All subscriptions',
    close: 'Close dialog', open: 'Open episode', reading: 'Read analysis', analyze: 'Episode analysis', description: 'Episode description',
    noDescription: 'No description is available. Open the episode to read its transcript.', previewEpisode: 'Preview episode', back: 'Back to episode cards',
    result: 'Showing', clickHint: 'Select a card for its full title and description', previous: 'Previous episode', next: 'Next episode', dragHint: 'Drag sideways · click a side card · use arrow keys',
    loading: 'Preparing your episode cards', loadingNote: 'Reading saved episodes and show artwork.', failure: 'Episodes are temporarily unavailable', failureNote: 'Check that PodMaster is running, then sign in and try again.',
    retry: 'Try again', login: 'Open PodMaster', empty: 'No matching episodes', emptyNote: 'Try another keyword or clear the filters.', reset: 'Clear filters',
    reference: 'Inspired by 21st', selected: 'Selected design', copied: 'Copied', copyFailure: 'Tell me the design number', detailLabel: 'EPISODE / PREVIEW',
    noDate: 'Unknown date', untitled: 'Untitled episode', chooseNotice: 'Your choice is saved locally. The actual dialog has not been changed.', noPeriod: 'No episodes in this period',
  },
};

const icons = {
  close: '<path d="m6 6 12 12M18 6 6 18"/>', search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
  file: '<path d="M14 3H6v18h12V7zM14 3v5h4M9 12h6M9 16h6"/>',
  check: '<path d="m5 12 4 4L19 6"/>', sparkle: '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/>',
  external: '<path d="M14 3h7v7M21 3l-9 9M10 3H3v18h18v-7"/>',
  left: '<path d="m14 6-6 6 6 6"/>', right: '<path d="m10 6 6 6-6 6"/>',
  collection: '<rect x="4" y="5" width="16" height="16" rx="3"/><path d="M8 2h8M8 10h8M8 15h5"/>',
};
const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name]}</svg>`;
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const panel = document.querySelector('#panel');
const dialog = document.querySelector('#fullscreen-dialog');
const periodStart = { week: '2026-09-21', month: '2026-09-01' };
const choiceKey = 'podmaster_briefing_dialog_choice';
const cache = new Map();
let feedsPromise;
const state = { language: 'zh', variant: 'grid', period: 'month', filter: 'all', source: 'all', query: '', focusId: null, activeIndex: 0, expandedId: null, loading: true, error: false, data: null, feeds: [], chosen: localStorage.getItem(choiceKey), requestVersion: 0 };
const t = key => translations[state.language][key];
const variantText = (variant, key) => variant[key][state.language === 'zh' ? 0 : 1];
const currentVariant = () => variants.find(variant => variant.id === state.variant);
const materials = () => state.data?.materials || [];
const analyzed = episode => episode.analysis_status === 'completed';
const announce = message => { document.querySelector('#announcement').textContent = message; };

function displayDate(value, options = { month: 'short', day: 'numeric' }) {
  if (!value) return t('noDate');
  return new Intl.DateTimeFormat(state.language === 'zh' ? 'zh-CN' : 'en-US', { timeZone: 'Asia/Hong_Kong', ...options }).format(new Date(value));
}

function periodLabel() {
  if (state.language === 'zh') return state.data?.period?.label || (state.period === 'month' ? '2026年09月 月报' : '2026.09.21 — 09.27 周报');
  return state.period === 'month' ? 'SEPTEMBER 2026 / MONTHLY' : 'SEP 21 — 27, 2026 / WEEKLY';
}

function cover(episode, extraClass = '') {
  const feed = state.feeds.find(item => item.title === episode.feed);
  const image = feed?.image;
  const initials = (episode.feed || 'P').slice(0, 2).toUpperCase();
  return `<span class="feed-cover ${extraClass}" style="--hue:${hue(episode.feed)}"><span>${escapeHtml(initials)}</span>${image ? `<img src="${escapeHtml(image)}" alt="" loading="lazy" decoding="async">` : ''}</span>`;
}

function hue(name = '') {
  return [...name].reduce((value, char) => value + char.charCodeAt(0), 0) % 360;
}

function description(episode) {
  const text = new DOMParser().parseFromString(episode.description || '', 'text/html').body.textContent.replace(/\s+/g, ' ').trim();
  if (!text) return t('noDescription');
  return text.length > 520 ? `${text.slice(0, 520)}…` : text;
}

function statuses(episode) {
  return `<span class="${episode.has_transcript ? '' : 'missing'}">${icon('file')}${t(episode.has_transcript ? 'transcript' : 'missing')}</span>${analyzed(episode) ? `<span class="complete">${icon('check')}${t('analyzed')}</span>` : ''}`;
}

function actions(episode) {
  const episodeUrl = `/episodes/${encodeURIComponent(episode.episode_id)}`;
  const readingUrl = `/briefing?period_type=${state.period}&period_start=${periodStart[state.period]}&mode=core&source=${encodeURIComponent(episode.source_id || '')}`;
  return `${episode.source_id ? `<a class="card-primary" href="${readingUrl}" target="_blank" rel="noopener">${icon('sparkle')}${t(analyzed(episode) ? 'reading' : 'analyze')}</a>` : ''}<a class="card-link" href="${episodeUrl}" target="_blank" rel="noopener">${t('open')}${icon('external')}</a>`;
}

function filteredEpisodes() {
  const query = state.query.trim().toLocaleLowerCase();
  return materials().filter(episode =>
    (state.filter !== 'transcript' || episode.has_transcript) &&
    (state.filter !== 'analyzed' || analyzed(episode)) &&
    (state.source === 'all' || episode.feed === state.source) &&
    (!query || `${episode.title} ${episode.feed}`.toLocaleLowerCase().includes(query)),
  );
}

function card(episode, index) {
  return `<article class="episode-card${state.variant === 'detail' && episode.episode_id === state.focusId ? ' active' : ''}" data-id="${escapeHtml(episode.episode_id)}">
    <div class="card-top">${cover(episode)}<div class="source-byline"><span class="source-name">${escapeHtml(episode.feed)}</span><span class="source-date">${displayDate(episode.published_at)}</span></div><span class="card-number">${String(index + 1).padStart(2, '0')}</span></div>
    <h3><button class="title-button" type="button" data-action="inspect" aria-label="${t('previewEpisode')}: ${escapeHtml(episode.title)}">${escapeHtml(episode.title || t('untitled'))}</button></h3>
    <div class="card-status">${statuses(episode)}</div><div class="card-actions">${actions(episode)}</div>
  </article>`;
}

function reading(episode, sidebar = false) {
  return `<section class="${sidebar ? 'side-reading' : 'detail-reading'}" aria-label="${t('previewEpisode')}">
    ${!sidebar ? `<button class="detail-back" data-action="back" type="button">${icon('left')}${t('back')}</button>` : ''}
    <div class="${sidebar ? '' : 'detail-heading'}">${cover(episode, 'reading-cover')}<div><p class="reading-eyebrow">${t('detailLabel')}</p><h3>${escapeHtml(episode.title || t('untitled'))}</h3><p class="reading-source">${escapeHtml(episode.feed)} · ${displayDate(episode.published_at)}</p></div></div>
    <div class="reading-status"><span>${t(episode.has_transcript ? 'transcript' : 'missing')}</span>${analyzed(episode) ? `<span>${t('analyzed')}</span>` : ''}</div>
    <p class="reading-label">${t('description')}</p><p class="reading-description">${escapeHtml(description(episode))}</p><div class="reading-actions">${actions(episode)}</div>
  </section>`;
}

function dateGroups(episodes) {
  const groups = new Map();
  episodes.forEach((episode, index) => {
    const key = episode.published_at ? displayDate(episode.published_at, { year: 'numeric', month: '2-digit', day: '2-digit' }) : 'unknown';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push({ episode, index });
  });
  return [...groups.values()].map(group => {
    const date = group[0].episode.published_at;
    const day = date ? new Intl.DateTimeFormat('en', { day: '2-digit', timeZone: 'Asia/Hong_Kong' }).format(new Date(date)) : '—';
    return `<section class="date-group"><div class="day-label"><strong>${day}</strong><span>${date ? displayDate(date, { month: 'short' }) : t('noDate')}</span></div><div class="day-cards">${group.map(({ episode, index }) => card(episode, index)).join('')}</div></section>`;
  }).join('');
}

function deckCard(episode, index, position) {
  return `<article class="deck-card ${position}" data-id="${escapeHtml(episode.episode_id)}" ${position !== 'current' ? `data-direction="${position === 'left' ? -1 : 1}"` : ''}>
    <div class="deck-art" style="--hue:${hue(episode.feed)}">${cover(episode)}</div><div class="deck-copy"><span class="source-name">${escapeHtml(episode.feed)} · ${displayDate(episode.published_at)}</span>
    <h3><button type="button" class="title-button" data-action="${position === 'current' ? 'inspect' : 'move'}" ${position === 'current' ? '' : `data-direction="${position === 'left' ? -1 : 1}"`}>${escapeHtml(episode.title)}</button></h3>
    <div class="card-status">${statuses(episode)}</div>${position === 'current' ? `<div class="card-actions">${actions(episode)}</div>` : ''}</div></article>`;
}

function deck(episodes) {
  state.activeIndex = Math.min(state.activeIndex, episodes.length - 1);
  const index = state.activeIndex;
  return `<div class="stack-layout"><div class="deck" tabindex="0" aria-label="${t('dragHint')}">
    ${index > 0 ? deckCard(episodes[index - 1], index - 1, 'left') : ''}${index < episodes.length - 1 ? deckCard(episodes[index + 1], index + 1, 'right') : ''}${deckCard(episodes[index], index, 'current')}
    </div><div class="deck-controls"><button class="deck-arrow" data-action="move" data-direction="-1" type="button" aria-label="${t('previous')}" ${index === 0 ? 'disabled' : ''}>${icon('left')}</button><span class="deck-count"><b>${String(index + 1).padStart(2, '0')}</b> / ${String(episodes.length).padStart(2, '0')}</span><button class="deck-arrow" data-action="move" data-direction="1" type="button" aria-label="${t('next')}" ${index === episodes.length - 1 ? 'disabled' : ''}>${icon('right')}</button></div>
    <p class="deck-caption">${t('dragHint')}</p><div class="deck-thumbs">${episodes.map((episode, i) => `<button class="deck-thumb${i === index ? ' active' : ''}" type="button" data-action="jump" data-index="${i}" aria-label="${escapeHtml(episode.title)}" aria-pressed="${i === index}">${cover(episode)}</button>`).join('')}</div></div>`;
}

function galleryCard(episode, index) {
  const expanded = episode.episode_id === state.expandedId;
  const image = state.feeds.find(feed => feed.title === episode.feed)?.image;
  return `<article class="episode-card gallery-card${expanded ? ' expanded' : ''}" data-id="${escapeHtml(episode.episode_id)}">
    <div class="gallery-art" style="--hue:${hue(episode.feed)}"><span class="ambient-art"${image ? ` style="--art:url('${escapeHtml(image.replace(/[()'"\\]/g, ''))}')"` : ''}></span>${cover(episode)}<span class="art-label">PODMASTER / COLLECTION</span><span class="art-number">${String(index + 1).padStart(2, '0')}</span></div>
    <div class="gallery-copy"><span class="source-name">${escapeHtml(episode.feed)} · ${displayDate(episode.published_at)}</span><h3><button class="title-button" data-action="inspect" type="button" aria-expanded="${expanded}">${escapeHtml(episode.title)}</button></h3><div class="card-status">${statuses(episode)}</div>
    ${expanded ? `<p class="reading-label">${t('description')}</p><p class="gallery-description">${escapeHtml(description(episode))}</p>` : ''}<div class="card-actions">${actions(episode)}</div></div></article>`;
}

function emptyState(kind) {
  const error = kind === 'error';
  const loading = kind === 'loading';
  return `<div class="empty-state">${icon('collection')}<h3>${t(loading ? 'loading' : error ? 'failure' : materials().length ? 'empty' : 'noPeriod')}</h3><p>${t(loading ? 'loadingNote' : error ? 'failureNote' : 'emptyNote')}</p>${loading ? '' : error ? `<button class="card-primary" data-action="retry" type="button">${t('retry')}</button><a class="card-link" href="/" target="_blank" rel="noopener">${t('login')}${icon('external')}</a>` : `<button class="card-primary" data-action="reset" type="button">${t('reset')}</button>`}</div>`;
}

function renderBody() {
  const episodes = filteredEpisodes();
  const body = panel.querySelector('.panel-body');
  let content;
  if (state.loading || state.error || !episodes.length) content = emptyState(state.loading ? 'loading' : state.error ? 'error' : 'empty');
  else if (state.focusId && !['detail', 'gallery'].includes(state.variant)) content = reading(materials().find(item => item.episode_id === state.focusId));
  else if (state.variant === 'grid') content = `<div class="cards-grid">${episodes.map(card).join('')}</div>`;
  else if (state.variant === 'date') content = dateGroups(episodes);
  else if (state.variant === 'detail') {
    if (!episodes.some(episode => episode.episode_id === state.focusId)) state.focusId = episodes[0].episode_id;
    content = `<div class="split-layout"><div class="split-cards">${episodes.map(card).join('')}</div>${reading(episodes.find(episode => episode.episode_id === state.focusId), true)}</div>`;
  } else if (state.variant === 'stack') content = deck(episodes);
  else content = `<div class="gallery-grid">${episodes.map(galleryCard).join('')}</div>`;
  body.innerHTML = content;
  body.querySelectorAll('img').forEach(img => img.addEventListener('error', () => {
    const name = img.closest('[data-id]')?.dataset.id;
    const episode = materials().find(item => item.episode_id === name);
    img.parentElement.textContent = (episode?.feed || 'P').slice(0, 2);
  }, { once: true }));
  panel.querySelector('#result-count').textContent = `${t('result')} ${episodes.length} / ${materials().length}`;
}

function renderPanel() {
  panel.className = `collection-panel v-${state.variant}`;
  panel.setAttribute('aria-label', t('heading'));
  const count = materials().length;
  const sourceOptions = [...new Set(materials().map(episode => episode.feed))];
  panel.innerHTML = `<header class="panel-header"><div><p class="period-eyebrow"><i></i>${escapeHtml(periodLabel())}</p><h2>${t('heading')}</h2><p class="panel-subtitle"><span>${t('total')} <b>${count}</b> ${t('episodes')}</span><span class="divider"></span><span>${t('transcript')} <b>${materials().filter(episode => episode.has_transcript).length}</b></span><span>${t('analyzed')} <b>${materials().filter(analyzed).length}</b></span></p></div><button class="panel-close" type="button" data-action="close" aria-label="${t('close')}">${icon('close')}</button></header>
    <div class="panel-controls"><div class="status-filters" aria-label="${t('all')}">${[['all', 'all'], ['transcript', 'withText'], ['analyzed', 'withAnalysis']].map(([filter, key]) => `<button type="button" class="filter-button${filter === state.filter ? ' active' : ''}" data-action="filter" data-filter="${filter}" aria-pressed="${filter === state.filter}">${t(key)}</button>`).join('')}</div><div class="search-tools"><label class="search-field">${icon('search')}<input type="search" id="episode-search" value="${escapeHtml(state.query)}" placeholder="${t('search')}" aria-label="${t('search')}"></label><select class="source-filter" id="source-filter" aria-label="${t('allSources')}"><option value="all">${t('allSources')}</option>${sourceOptions.map(source => `<option value="${escapeHtml(source)}"${source === state.source ? ' selected' : ''}>${escapeHtml(source)}</option>`).join('')}</select></div></div>
    <div class="panel-body"></div><footer class="panel-foot"><span id="result-count"></span><span>${state.variant === 'stack' ? `<kbd>← →</kbd>${t('dragHint')}` : t('clickHint')}</span></footer>`;
  renderBody();
}

function renderPage() {
  const variant = currentVariant();
  document.documentElement.lang = state.language === 'zh' ? 'zh-CN' : 'en';
  document.querySelectorAll('[data-text]').forEach(element => { element.textContent = t(element.dataset.text); });
  const language = document.querySelector('#language');
  language.textContent = state.language === 'zh' ? 'EN' : '中文';
  language.setAttribute('aria-label', state.language === 'zh' ? 'Switch to English' : '切换到中文');
  document.querySelector('#variants').innerHTML = variants.map(item => `<button type="button" class="variant-option${item.id === state.variant ? ' active' : ''}" data-variant="${item.id}" aria-pressed="${item.id === state.variant}"><span class="option-heading"><span class="option-number">${item.number}</span>${variantText(item, 'title')}</span><span class="option-description">${variantText(item, 'caption')}</span>${state.chosen === item.id ? `<span class="option-picked" aria-label="${t('selected')}">${icon('check')}</span>` : ''}</button>`).join('');
  document.querySelector('#preview-title').textContent = `${variant.number} / ${variantText(variant, 'title')}`;
  document.querySelector('#rationale-index').textContent = variant.number;
  document.querySelector('#rationale-title').textContent = variantText(variant, 'title');
  document.querySelector('#rationale-copy').textContent = variantText(variant, 'rationale');
  const reference = document.querySelector('#reference');
  reference.href = variant.reference;
  reference.textContent = `${t('reference')} ↗`;
  const selected = variants.find(item => item.id === state.chosen);
  document.querySelector('#choice-label').textContent = selected ? `${t('selected')} ${selected.number}` : '';
  document.querySelector('#copy-choice').hidden = !selected;
  document.querySelectorAll('[data-period]').forEach(button => {
    button.classList.toggle('active', button.dataset.period === state.period);
    button.setAttribute('aria-pressed', button.dataset.period === state.period);
  });
  renderPanel();
}

async function readApi(url) {
  const token = localStorage.getItem('podcast_auth_token');
  const response = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const result = await response.json();
  if (!result.success) throw new Error('Unable to read saved episodes');
  return result.data;
}

async function loadPeriod() {
  const requestVersion = ++state.requestVersion;
  state.loading = true;
  state.error = false;
  state.data = null;
  renderPage();
  try {
    if (!feedsPromise) feedsPromise = readApi('/api/feeds?per_page=100&page=1');
    if (!cache.has(state.period)) cache.set(state.period, readApi(`/api/briefing-reports/modes?period_type=${state.period}&period_start=${periodStart[state.period]}`));
    const [data, feeds] = await Promise.all([cache.get(state.period), feedsPromise]);
    if (requestVersion !== state.requestVersion) return;
    state.data = data;
    state.feeds = feeds;
  } catch {
    if (requestVersion !== state.requestVersion) return;
    cache.delete(state.period);
    feedsPromise = undefined;
    state.error = true;
  }
  if (requestVersion !== state.requestVersion) return;
  state.loading = false;
  renderPage();
}

function resetBrowse() {
  state.focusId = null;
  state.activeIndex = 0;
  state.expandedId = null;
}

function openPreview() {
  panel.hidden = false;
  document.querySelector('#reopen').hidden = true;
}

function moveDeck(direction) {
  const count = filteredEpisodes().length;
  const index = Math.max(0, Math.min(count - 1, state.activeIndex + direction));
  if (!count || index === state.activeIndex) return;
  state.activeIndex = index;
  renderBody();
  panel.querySelector('.deck').focus({ preventScroll: true });
  const thumbs = panel.querySelector('.deck-thumbs');
  const activeThumb = thumbs.querySelector('.active');
  thumbs.scrollLeft += activeThumb.getBoundingClientRect().left - thumbs.getBoundingClientRect().left - (thumbs.clientWidth - activeThumb.offsetWidth) / 2;
  announce(filteredEpisodes()[index].title);
}

document.addEventListener('click', async event => {
  const variant = event.target.closest('[data-variant]');
  const period = event.target.closest('[data-period]');
  const action = event.target.closest('[data-action]');
  if (variant) {
    state.variant = variant.dataset.variant;
    resetBrowse();
    openPreview();
    renderPage();
    return;
  }
  if (period && period.dataset.period !== state.period) {
    state.period = period.dataset.period;
    state.source = 'all';
    resetBrowse();
    await loadPeriod();
    return;
  }
  if (action?.dataset.action === 'close') {
    if (dialog.open) dialog.close();
    else { panel.hidden = true; document.querySelector('#reopen').hidden = false; document.querySelector('#reopen').focus(); }
    return;
  }
  if (action?.dataset.action === 'retry') { await loadPeriod(); return; }
  if (action?.dataset.action === 'filter' || action?.dataset.action === 'reset') {
    state.filter = action.dataset.filter || 'all';
    if (action.dataset.action === 'reset') { state.source = 'all'; state.query = ''; }
    resetBrowse();
    renderPanel();
    return;
  }
  if (action?.dataset.action === 'back') { state.focusId = null; renderBody(); return; }
  if (action?.dataset.action === 'move') { moveDeck(Number(action.dataset.direction)); return; }
  if (action?.dataset.action === 'jump') { moveDeck(Number(action.dataset.index) - state.activeIndex); return; }
  const cardElement = event.target.closest('article[data-id]');
  if (cardElement && !event.target.closest('a')) {
    if (cardElement.dataset.direction) { moveDeck(Number(cardElement.dataset.direction)); return; }
    const id = cardElement.dataset.id;
    if (state.variant === 'gallery') state.expandedId = state.expandedId === id ? null : id;
    else state.focusId = id;
    renderBody();
    if (state.variant === 'detail') panel.querySelector('.side-reading').scrollIntoView({ block: 'nearest' });
    else if (state.variant === 'gallery') panel.querySelector('.gallery-card.expanded')?.scrollIntoView({ block: 'nearest' });
    else panel.querySelector('.panel-body').scrollTop = 0;
  }
});

panel.addEventListener('input', event => {
  if (event.target.id !== 'episode-search') return;
  state.query = event.target.value;
  resetBrowse();
  renderBody();
});
panel.addEventListener('change', event => {
  if (event.target.id !== 'source-filter') return;
  state.source = event.target.value;
  resetBrowse();
  renderBody();
});

let dragStart = null;
let dragged = false;
panel.addEventListener('pointerdown', event => {
  dragged = false;
  if (state.variant !== 'stack' || event.button !== 0 || !event.target.closest('.deck-card.current') || event.target.closest('a,button')) return;
  dragStart = { x: event.clientX, y: event.clientY, pointer: event.pointerId };
  panel.setPointerCapture(event.pointerId);
});
panel.addEventListener('pointerup', event => {
  if (!dragStart) return;
  const dx = event.clientX - dragStart.x;
  const dy = event.clientY - dragStart.y;
  dragStart = null;
  if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy)) { dragged = true; moveDeck(dx > 0 ? -1 : 1); }
});
panel.addEventListener('pointercancel', () => { dragStart = null; });
panel.addEventListener('click', event => {
  if (dragged) { event.stopPropagation(); dragged = false; }
});
document.addEventListener('keydown', event => {
  if (state.variant !== 'stack' || panel.hidden || state.focusId || !panel.contains(document.activeElement) || event.target.closest('input,select,a') || !['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
  event.preventDefault();
  moveDeck(event.key === 'ArrowLeft' ? -1 : 1);
});

document.querySelector('#language').addEventListener('click', () => { state.language = state.language === 'zh' ? 'en' : 'zh'; renderPage(); });
document.querySelector('#reopen').addEventListener('click', openPreview);
document.querySelector('#fullscreen').addEventListener('click', () => {
  openPreview();
  document.querySelector('#fullscreen-stage').append(panel);
  dialog.showModal();
});
document.querySelector('#leave-fullscreen').addEventListener('click', () => dialog.close());
dialog.addEventListener('close', () => document.querySelector('#preview-stage').append(panel));
document.querySelector('#choose').addEventListener('click', () => {
  state.chosen = state.variant;
  localStorage.setItem(choiceKey, state.chosen);
  renderPage();
  announce(t('chooseNotice'));
});
document.querySelector('#copy-choice').addEventListener('click', async () => {
  const selected = variants.find(item => item.id === state.chosen);
  const text = `我选方案 ${selected.number}：${selected.title[0]}，请替换周报和月报的节目弹窗。`;
  try {
    await navigator.clipboard.writeText(text);
    document.querySelector('#copy-choice').textContent = t('copied');
    announce(t('copied'));
  } catch {
    document.querySelector('#choice-label').textContent = `${t('copyFailure')} ${selected.number}`;
    announce(text);
  }
});

loadPeriod();
