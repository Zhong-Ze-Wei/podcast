import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  AlertCircle, ArrowLeft, Check, ChevronDown, Download, ExternalLink,
  Heart, Loader2, Menu, MoreHorizontal, X,
} from 'lucide-react';
import { briefingLabApi, briefingReportsApi } from '../../services/api';
import FeedImage from '../common/FeedImage';
import './briefing-reports.css';
import './briefing-modes.css';

const LAYOUTS = [
  { id: 'space', name: '留白', description: '一句主角，几句留给慢读' },
  { id: 'large', name: '大字', description: '原话铺开，一句一句读' },
  { id: 'list', name: '清单', description: '顺着读，快速挑想听的' },
  { id: 'columns', name: '双栏', description: '并排读，看看观点的不同' },
  { id: 'paper', name: '纸面', description: '一张可以带走的阅读页' },
  { id: 'newspaper', name: '报刊', description: '暖白双栏，像读一份报刊' },
  { id: 'notes', name: '便笺', description: '浅色便笺，一条一个重点' },
];
const MODES = [
  { id: 'core', name: '核心提要' }, { id: 'quotes', name: '原话精选' },
  { id: 'connections', name: '共性与分歧' }, { id: 'concepts', name: '新词与方法' },
  { id: 'resources', name: '提到的资料' },
];
const TOPIC_TAGS = ['AI', '编程', '商业', '管理', '历史', '科学'];
const KIND_LABELS = { insight: 'AI 提要', connection: 'AI 归纳', concept: '新词与方法', resource: '节目资料' };
const CONNECTION_LABELS = { commonality: '共性', difference: '分歧', complementary: '互补' };
const RESOURCE_LABELS = { book: '书', article: '文章', paper: '论文', tool: '工具', website: '网站', report: '报告', podcast: '播客' };

function payload(response) { return response?.data ?? response; }
function timeText(value) {
  if (value == null || !Number.isFinite(Number(value))) return '';
  const seconds = Math.floor(Number(value));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds % 3600 / 60);
  return `${hours ? `${hours}:` : ''}${hours ? String(minutes).padStart(2, '0') : minutes}:${String(seconds % 60).padStart(2, '0')}`;
}
function dateText(value) {
  return value ? new Date(value).toLocaleDateString('zh-CN', { timeZone: 'Asia/Hong_Kong', month: 'long', day: 'numeric' }) : '';
}
function readStored(storage, key, fallback) {
  const stored = storage.getItem(key);
  if (!stored) return fallback;
  try { return JSON.parse(stored); } catch { storage.removeItem(key); return fallback; }
}
function usableUrl(url) { return typeof url === 'string' && /^https?:\/\//i.test(url) ? url : null; }
function coverUrl(url) { return usableUrl(url) || (typeof url === 'string' && /^\/api\/media\/covers\/[^/]+\.(?:jpe?g|png|webp)(?:[?#].*)?$/i.test(url) ? url : null); }
function itemsIn(report) { return (report?.sections || []).flatMap(section => section.items || []); }
async function migrateQuoteFavorites(saved, snapshot) {
  if (!saved.some(id => /^S\d+-C/.test(id))) return saved;
  const previous = payload(await briefingReportsApi.edition()).edition;
  if (previous?.corpus_id !== snapshot.corpus.id) return saved;
  const oldQuotes = itemsIn(previous).filter(card => card.kind === 'quote' && saved.includes(card.id));
  const currentQuotes = itemsIn(snapshot.reports.quotes);
  const matches = oldQuotes.map(old => currentQuotes.find(card => card.episode_id === old.episode_id && card.quote === old.quote)?.id).filter(Boolean);
  return [...new Set([...saved, ...matches])];
}
async function errorText(error, fallback) {
  if (error instanceof Blob) {
    try { return JSON.parse(await error.text()).message || fallback; } catch { return fallback; }
  }
  return error?.message || fallback;
}

function useModalFocus(ref, onClose) {
  useEffect(() => {
    const before = document.activeElement;
    const selectable = () => Array.from(ref.current?.querySelectorAll('button:not([disabled]), a[href], input, select, textarea, iframe, [tabindex="0"]') || []);
    selectable()[0]?.focus();
    const onKey = event => {
      if (event.key === 'Escape') onClose();
      if (event.key !== 'Tab') return;
      const elements = selectable();
      const first = elements[0];
      const last = elements.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); before?.focus(); };
  }, [ref, onClose]);
}

function Cover({ source, feeds, large = false }) {
  const feed = feeds.find(item => item.id === source?.feed_id || item.title === source?.feed);
  const sourceImage = coverUrl(source?.image || source?.image_url);
  const feedImage = coverUrl(source?.feed_image || feed?.image || feed?.image_url);
  const image = sourceImage?.startsWith('/api/media/') ? sourceImage : feedImage?.startsWith('/api/media/') ? feedImage : sourceImage || feedImage;
  return <FeedImage feed={{ ...feed, type: feed?.type || source?.source_type, image, title: source?.feed || feed?.title || '' }} fallbackImage={feedImage} className={`br-cover ${large ? 'br-cover-large' : ''}`} />;
}

function OriginalQuote({ card }) {
  return <>
    {card.translation && <span className="br-translation-label">译文</span>}
    <blockquote>{card.translation || card.quote}</blockquote>
  </>;
}

function QuoteEvidence({ card, sources, onRead, onListen, onSource }) {
  const source = sources.find(item => item.id === card.source_id) || {};
  const episodeId = card.episode_id || source.episode_id;
  return <section className="br-card-evidence-quote">
    <OriginalQuote card={card} />
    <div className="br-evidence-source"><strong>{card.feed || source.feed}</strong>{card.speaker && <span>{card.speaker}</span>}<span title={card.source_title || source.title}>{card.source_title || source.title}</span></div>
    <div className="br-evidence-actions"><button className="br-text-button" onClick={() => onRead(card.source_id)}>读这期</button>{episodeId && <button className="br-text-button" onClick={() => onListen({ ...card, episode_id: episodeId, original_url: source.original_url || source.url || source.link })}>从 {timeText(card.start) || '开头'} 听</button>}<button className="br-text-button" onClick={() => onSource(card)}>在文稿中查看</button>{card.translation && <details className="br-inline-original"><summary>英文原话</summary><p lang="en">{card.quote}</p></details>}</div>
  </section>;
}

function Excerpt({ card, sources, feeds, onRead, onListen, onSource, savedQuotes, onToggleQuote, onCopy, onTag, selectedTag, evidenceOpen, onEvidenceToggle }) {
  const source = sources.find(item => item.id === card.source_id) || {};
  const episodeId = card.episode_id || source.episode_id;
  const episodeTitle = card.source_title || source.title;
  const favoriteKey = card.id;
  const saved = savedQuotes.includes(favoriteKey);
  const isQuote = card.kind === 'quote';
  const evidence = card.evidence || (!isQuote && card.quote ? [card] : []);
  const evidenceCount = new Set(evidence.map(quote => quote.source_id)).size;
  const listen = () => onListen({ ...card, episode_id: episodeId, original_url: source.original_url || source.url || source.link });
  return <article className={`br-excerpt br-mode-card br-item-${card.kind}`} data-item-id={card.id} data-quote-id={isQuote ? card.id : undefined}>
    <div className="br-excerpt-heading">{isQuote ? (card.brief || card.context) && <p className="br-brief">{card.brief || card.context}</p> : <span className="br-card-kicker">{card.kind === 'connection' ? `${CONNECTION_LABELS[card.relation] || '联系'} · ${evidenceCount} 期节目` : card.kind === 'resource' ? `${RESOURCE_LABELS[card.resource_kind] || '资料'} · ${['recommended', 'explicit_recommendation'].includes(card.relation) ? '嘉宾推荐' : '节目提到'}` : KIND_LABELS[card.kind]}</span>}</div>
    <div className="br-excerpt-words">{isQuote ? <OriginalQuote card={card} /> : <><h2 className="br-mode-card-title">{card.title}</h2><p className="br-mode-card-text">{card.text}</p>{card.kind === 'resource' && usableUrl(card.url) && <a className="br-text-button br-open-resource" href={card.url} target="_blank" rel="noopener noreferrer">打开资料 <ExternalLink size={14} /></a>}</>}</div>
    {card.topic_tags?.length > 0 && <div className="br-card-tags">{card.topic_tags.map(tag => <button key={tag} aria-pressed={selectedTag === tag} className={selectedTag === tag ? 'is-active' : ''} onClick={() => onTag(selectedTag === tag ? '' : tag)}>{tag}</button>)}</div>}
    {evidence.length > 0 && <details className="br-card-evidence" open={evidenceOpen.includes(card.id)} onToggle={event => onEvidenceToggle(card.id, event.currentTarget.open)}><summary>{card.kind === 'resource' ? '提及原话' : '原话依据'} <span>{evidence.length} 段</span><ChevronDown size={14} /></summary><div>{evidence.map(quote => <QuoteEvidence key={quote.id} card={quote} sources={sources} onRead={onRead} onListen={onListen} onSource={onSource} />)}</div></details>}
    <footer className="br-excerpt-footer">
      <div className="br-source-identity"><Cover source={{ ...source, feed: card.feed || source.feed }} feeds={feeds} /><div className="br-source-info"><div className="br-source-byline"><strong>{card.feed || source.feed || '来源节目'}</strong>{card.speaker && <span>{card.speaker}</span>}</div>{episodeTitle && <span className="br-source-episode" title={episodeTitle}>{episodeTitle}</span>}</div></div>
      <div className="br-excerpt-actions">
        <button className="br-text-button" onClick={() => onRead(card.source_id)}>读这期</button>
        {episodeId && <button className="br-text-button br-listen" onClick={listen}>从 {timeText(card.start) || '开头'} 听</button>}
        <button className={`br-favorite-button ${saved ? 'is-saved' : ''}`} aria-label={saved ? '取消收藏此条内容' : '收藏此条内容'} title={saved ? '已收藏，点击取消' : '收藏到此浏览器'} aria-pressed={saved} onClick={() => onToggleQuote(favoriteKey)}><Heart size={19} fill={saved ? 'currentColor' : 'none'} /></button>
        <details className="br-more"><summary aria-label="更多内容操作" title="更多内容操作"><MoreHorizontal size={19} /></summary><div className="br-more-menu">
          {isQuote && card.translation && <details className="br-inline-original"><summary>英文原话</summary><p lang="en">{card.quote}</p></details>}
          <button onClick={event => { onSource(isQuote || !evidence.length ? card : evidence[0]); event.currentTarget.closest('.br-more').open = false; }}>在文稿中查看</button>
          {isQuote && <button onClick={() => onCopy(card)}>复制原话与出处</button>}
        </div></details>
      </div>
    </footer>
  </article>;
}

function EpisodeReading({ data, loading, error, working, feeds, onGenerate, onSource, onListen, onRetry }) {
  const source = data?.source || {};
  const reading = data?.reading;
  return <article className="br-reading">
    <header className="br-reading-heading"><Cover source={source} feeds={feeds} large /><div><p>{source.feed}{source.duration > 0 ? ` · ${timeText(source.duration)}` : ''}</p><h1>{source.title || '正在读取节目'}</h1></div></header>
    {loading ? <div className="br-loading"><Loader2 size={18} className="br-spinning" />读取这期解读</div> : error ? <div className="br-notice br-notice-error" role="alert"><span>{error}</span><button className="br-text-button" onClick={onRetry}>重新加载</button></div> : !reading ? <section className="br-reading-empty"><h2>这期还没有单篇解读</h2><p>从已保存的文稿提炼少量要点，每个要点都附原话。</p><button className="br-button br-button-primary" disabled={working} onClick={onGenerate}>{working && <Loader2 size={15} className="br-spinning" />}生成这期解读</button><button className="br-text-button" onClick={() => onSource({ source_id: source.id, source_title: source.title, feed: source.feed, episode_id: source.episode_id })}>先读文稿</button></section> : <>
      <section className="br-reading-takeaway"><span className="br-reading-label">这期在说什么 · AI 解读</span><h2>{reading.takeaway}</h2></section>
      <section className="br-reading-points" aria-label={reading.points_label || '部分精选片段'}><span className="br-reading-label">{reading.points_label || '部分精选片段'}</span>{reading.points.map((point, index) => <details className="br-reading-point" key={index}><summary><div><h3>{point.title}</h3><p>{point.meaning}</p></div><span className="br-evidence-toggle">原话 <ChevronDown size={16} /></span></summary><div className="br-reading-evidence"><OriginalQuote card={point.quote} /><div className="br-reading-quote-actions">{point.quote.translation && <details className="br-inline-original"><summary>英文原话</summary><p lang="en">{point.quote.quote}</p></details>}<button className="br-text-button" onClick={() => onSource(point.quote)}>在文稿中查看</button>{source.episode_id && <button className="br-text-button" onClick={() => onListen({ ...point.quote, episode_id: source.episode_id, original_url: source.original_url || source.url || source.link })}>从 {timeText(point.quote.start) || '开头'} 听</button>}</div></div></details>)}</section>
      {reading.resources?.length > 0 && <details className="br-reading-resources"><summary>这期提到的资料 <span>{reading.resources.length} 份</span><ChevronDown size={16} /></summary><div>{reading.resources.map(resource => <section key={resource.id}><span className="br-reading-label">{RESOURCE_LABELS[resource.resource_kind] || '资料'} · {['recommended', 'explicit_recommendation'].includes(resource.relation) ? '嘉宾推荐' : '节目提到'}</span><h3>{resource.title}</h3>{resource.text && <p>{resource.text}</p>}<div className="br-reading-quote-actions">{usableUrl(resource.url) && <a className="br-text-button" href={resource.url} target="_blank" rel="noopener noreferrer">打开资料 <ExternalLink size={14} /></a>}<button className="br-text-button" onClick={() => onSource(resource)}>查看提及原话</button></div></section>)}</div></details>}
      <footer className="br-reading-footer"><button className="br-text-button" onClick={() => onSource({ source_id: source.id, source_title: source.title, feed: source.feed, episode_id: source.episode_id })}>读完整文稿</button><span>解读生成于 {dateText(reading.generated_at)}</span><button className="br-text-button" disabled={working} onClick={onGenerate}>重新解读</button></footer>
    </>}
  </article>;
}

function SourceDrawer({ selection, onClose, onOpenEpisode, onListen }) {
  const [source, setSource] = useState(null);
  const [error, setError] = useState('');
  const ref = useRef(null);
  const bodyRef = useRef(null);
  useModalFocus(ref, onClose);
  useEffect(() => {
    let active = true;
    setSource(null); setError('');
    briefingLabApi.source(selection.source_id).then(response => { if (active) setSource(payload(response)); }).catch(err => { if (active) setError(err.message || '原文暂时无法读取。'); });
    return () => { active = false; };
  }, [selection.source_id]);
  useEffect(() => { if (source) bodyRef.current?.querySelector('.br-highlighted')?.scrollIntoView({ block: 'center' }); }, [source, selection]);
  const quote = selection.quote;
  const segments = source?.segments || [];
  const exactOffset = Number.isInteger(selection.offset) && source?.full_text?.slice(selection.offset, selection.offset + (quote?.length || 0)) === quote;
  const offset = exactOffset ? selection.offset : quote && source?.full_text ? source.full_text.indexOf(quote) : -1;
  const timeSegment = selection.start != null ? segments.findIndex((segment, index) => Number(segment.start ?? segment.time ?? 0) <= selection.start && Number(segment.end ?? segments[index + 1]?.start ?? Infinity) > selection.start) : -1;
  const exactSegment = quote ? segments.findIndex(segment => segment.text?.includes(quote)) : -1;
  const timedHighlight = timeSegment >= 0 ? timeSegment : exactSegment;
  return createPortal(<div className="br-modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}><aside className="br-source-drawer" ref={ref} role="dialog" aria-modal="true" aria-labelledby="br-source-title">
    <div className="br-modal-heading"><div><span className="br-field-label">{source?.feed || selection.feed || '节目文稿'}</span><h2 id="br-source-title">{source?.title || selection.source_title || '正在读取原文'}</h2></div><button className="br-icon-button" onClick={onClose} aria-label="关闭原文"><X size={19} /></button></div>
    <div className="br-drawer-toolbar">{(selection.episode_id || source?.episode_id) && <><button className="br-button" onClick={() => { onClose(); onOpenEpisode(selection.episode_id || source.episode_id); }}>打开节目</button><button className="br-button" onClick={() => onListen({ ...selection, episode_id: selection.episode_id || source.episode_id, original_url: source?.original_url })}>从 {timeText(selection.start) || '开头'} 听</button></>}</div>
    <div className="br-source-body custom-scrollbar" ref={bodyRef}>{error ? <div className="br-notice br-notice-error" role="alert">{error}</div> : !source ? <div className="br-loading"><Loader2 size={18} className="br-spinning" />读取已保存文稿</div> : <>
      {quote && <div className="br-selected-quote"><strong>这句话的原文{selection.start != null ? ` · ${timeText(selection.start)}` : ''}</strong><p>{quote}</p></div>}
      {segments.length ? segments.map((segment, index) => { const quoteIndex = quote && index === timedHighlight ? segment.text?.indexOf(quote) : -1; return <div className={`br-transcript-segment ${index === timedHighlight ? 'br-highlighted' : ''}`} key={index}><span>{timeText(segment.start ?? segment.time)}{segment.speaker ? ` · ${segment.speaker}` : ''}</span><p>{quoteIndex >= 0 ? <>{segment.text.slice(0, quoteIndex)}<mark>{quote}</mark>{segment.text.slice(quoteIndex + quote.length)}</> : segment.text}</p></div>; }) : <div className="br-full-text">{offset >= 0 ? <>{source.full_text.slice(0, offset)}<mark className="br-highlighted">{quote}</mark>{source.full_text.slice(offset + quote.length)}</> : source.full_text}</div>}
    </>}</div>
  </aside></div>, document.body);
}

function PdfPreview({ report, pages, onPagesChange, onClose, onDownload, downloading, exportError }) {
  const [html, setHtml] = useState('');
  const [error, setError] = useState('');
  const ref = useRef(null);
  useModalFocus(ref, onClose);
  useEffect(() => {
    let active = true;
    setHtml(''); setError('');
    briefingReportsApi.html(report.id, pages).then(response => { if (active) setHtml(typeof response === 'string' ? response : payload(response)); }).catch(async err => { if (active) setError(await errorText(err, '报告预览暂时无法生成。')); });
    return () => { active = false; };
  }, [report.id, pages]);
  return createPortal(<div className="br-modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}><section className="br-pdf-modal" ref={ref} role="dialog" aria-modal="true" aria-labelledby="br-pdf-title">
    <div className="br-modal-heading"><div><h2 id="br-pdf-title">{report.title} · PDF 预览</h2><p>导出当前模式的一页或两页报告；页面筛选不会改变导出范围。</p></div><button className="br-icon-button" onClick={onClose} aria-label="关闭PDF预览"><X size={19} /></button></div>
    <div className="br-pdf-toolbar"><div className="br-segmented"><button className={pages === 1 ? 'is-active' : ''} onClick={() => onPagesChange(1)}>一页精选</button><button className={pages === 2 ? 'is-active' : ''} onClick={() => onPagesChange(2)}>两页报告</button></div><button className="br-button br-button-primary" disabled={downloading || !html} onClick={onDownload}>{downloading ? <Loader2 size={14} className="br-spinning" /> : <Download size={14} />}下载 PDF</button></div>
    {exportError && <div className="br-notice br-notice-error br-pdf-error" role="alert">{exportError}</div>}
    <div className="br-pdf-preview">{error ? <div className="br-notice br-notice-error" role="alert">{error}</div> : !html ? <div className="br-loading"><Loader2 size={18} className="br-spinning" />排版中</div> : <iframe title={`${pages}页${report.title}预览`} srcDoc={html} sandbox="allow-popups allow-popups-to-escape-sandbox" />}</div>
  </section></div>, document.body);
}

export default function BriefingReportsView({ currentUser, feeds = [], onOpenEpisode, onListen, onOpenMenu, hasPlayer = false }) {
  const userId = currentUser?.id || currentUser?._id || 'guest';
  const storagePrefix = `podmaster_briefing_reading:${userId}`;
  const [layout, setLayout] = useState('paper');
  const [mode, setMode] = useState('core');
  const [selectedTag, setSelectedTag] = useState('');
  const [savedOnly, setSavedOnly] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [topic, setTopic] = useState('');
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [task, setTask] = useState(null);
  const [progress, setProgress] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [pollError, setPollError] = useState('');
  const [selection, setSelection] = useState(null);
  const [preview, setPreview] = useState(false);
  const [pages, setPages] = useState(1);
  const [downloading, setDownloading] = useState(false);
  const [exportError, setExportError] = useState('');
  const [toast, setToast] = useState('');
  const [savedQuotes, setSavedQuotes] = useState([]);
  const [readingSource, setReadingSource] = useState(null);
  const [readings, setReadings] = useState({});
  const [readingLoading, setReadingLoading] = useState(false);
  const [readingError, setReadingError] = useState('');
  const [evidenceOpen, setEvidenceOpen] = useState([]);
  const viewRef = useRef(null);
  const userIdRef = useRef(userId);
  const readingScrollRef = useRef(0);
  userIdRef.current = userId;
  const modes = snapshot?.modes || MODES;
  const info = modes.find(item => item.id === mode) || MODES[0];
  const report = snapshot?.reports?.[mode];
  const sources = report?.sources || snapshot?.sources || [];
  const allItems = itemsIn(report);
  const isSaved = card => savedQuotes.includes(card.id);
  const filteredItems = allItems.filter(card => (!selectedTag || card.topic_tags?.includes(selectedTag)) && (!savedOnly || isSaved(card)));
  const visibleItems = showAll ? filteredItems : filteredItems.slice(0, 6);
  const matchingSourceCount = new Set(filteredItems.flatMap(card => [card.source_id, ...(card.source_ids || []), ...(card.evidence || []).map(quote => quote.source_id)]).filter(Boolean)).size;
  const prompt = report?.prompt || snapshot?.mode_prompts?.[mode]?.prompt || info.prompt;
  const inputDescription = report?.input_description || snapshot?.mode_prompts?.[mode]?.input_description || info.input_description;
  const working = Boolean(task || submitting);
  const closeSource = useCallback(() => setSelection(null), []);
  const closePreview = useCallback(() => setPreview(false), []);
  const reload = useCallback(async () => { const data = payload(await briefingReportsApi.modes()); if (userIdRef.current === userId) setSnapshot(data); return data; }, [userId]);
  const readEpisode = sourceId => { readingScrollRef.current = viewRef.current?.scrollTop || 0; setReadingSource(sourceId); setReadingError(''); };
  useLayoutEffect(() => { viewRef.current?.scrollTo({ top: readingSource ? 0 : readingScrollRef.current }); }, [readingSource]);

  useEffect(() => {
    let active = true;
    readingScrollRef.current = 0;
    setLoading(true); setSnapshot(null); setReadingSource(null); setReadings({}); setError(''); setPreview(false); setSelection(null); setProgress(null); setPollError(''); setSubmitting(false); setReadingLoading(false); setDownloading(false); setExportError(''); setEvidenceOpen([]); setSelectedTag(''); setSavedOnly(false); setShowAll(false);
    const storedLayout = localStorage.getItem(`${storagePrefix}:layout`);
    setLayout(LAYOUTS.some(item => item.id === storedLayout) ? storedLayout : 'paper');
    const storedMode = localStorage.getItem(`${storagePrefix}:mode`);
    const initialMode = MODES.some(item => item.id === storedMode) ? storedMode : 'core';
    setMode(initialMode);
    const savedTopic = readStored(sessionStorage, `${storagePrefix}:topic`, null);
    setTopic(savedTopic || '');
    setTask(readStored(sessionStorage, `${storagePrefix}:task`, null));
    const saved = readStored(localStorage, `${storagePrefix}:quotes`, []);
    setSavedQuotes(saved);
    briefingReportsApi.modes().then(async response => {
      if (!active) return;
      const data = payload(response);
      setSnapshot(data);
      if (savedTopic === null) setTopic(data.reports?.[initialMode]?.topic || '');
      // 旧收藏只有候选编号；用旧报告中的真实节目和原话核对，不能按 S01 序号猜新内容。
      let migrated = saved;
      try { migrated = await migrateQuoteFavorites(saved, data); } catch { /* 旧报告暂不可读时保留原收藏，仍可阅读当前简报。 */ }
      if (active && migrated.length !== saved.length) { setSavedQuotes(migrated); localStorage.setItem(`${storagePrefix}:quotes`, JSON.stringify(migrated)); }
    }).catch(err => { if (active) setError(err.message || '简报暂时无法加载。'); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [storagePrefix]);
  useEffect(() => { if (!loading) localStorage.setItem(`${storagePrefix}:layout`, layout); }, [layout, loading, storagePrefix]);
  useEffect(() => { if (!loading) localStorage.setItem(`${storagePrefix}:mode`, mode); }, [mode, loading, storagePrefix]);
  useEffect(() => { if (!loading) sessionStorage.setItem(`${storagePrefix}:topic`, JSON.stringify(topic)); }, [topic, loading, storagePrefix]);
  useEffect(() => {
    if (loading) return;
    if (task) sessionStorage.setItem(`${storagePrefix}:task`, JSON.stringify(task));
    else sessionStorage.removeItem(`${storagePrefix}:task`);
  }, [task, loading, storagePrefix]);
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(''), 3000); return () => clearTimeout(timer); }, [toast]);
  useEffect(() => { setEvidenceOpen([]); setPreview(false); }, [report?.id]);
  useEffect(() => { setShowAll(false); }, [mode, selectedTag, savedOnly, report?.id]);
  useEffect(() => {
    if (!readingSource) return;
    let active = true;
    setReadingLoading(true); setReadingError('');
    briefingReportsApi.reading(readingSource).then(response => { if (active) setReadings(previous => ({ ...previous, [readingSource]: payload(response) })); }).catch(err => { if (active) setReadingError(err.message || '这期解读暂时无法读取。'); }).finally(() => { if (active) setReadingLoading(false); });
    return () => { active = false; };
  }, [readingSource]);
  useEffect(() => {
    if (!task || loading) return;
    let active = true;
    let pending = false;
    const poll = async () => {
      if (pending) return;
      pending = true;
      try {
        const state = payload(await briefingReportsApi.task(task.id));
        if (!active) return;
        setProgress(state); setPollError('');
        if (state.status === 'completed') {
          if (state.result?.reports) setSnapshot(previous => ({ ...previous, reports: { ...previous?.reports, ...state.result.reports } }));
          if (state.result?.reading) { const reading = state.result.reading; setReadings(previous => ({ ...previous, [reading.source_id]: { ...previous[reading.source_id], reading, source: reading.source } })); }
          setTask(null); setProgress(null);
          if (task.kind !== 'reading') { try { await reload(); } catch { if (active) setError('简报已生成，列表暂未刷新。请重新加载。'); } }
        } else if (['failed', 'cancelled'].includes(state.status)) {
          setError(state.error || '本次生成未完成，之前的内容仍可阅读。'); setTask(null); setProgress(null);
        }
      } catch (err) {
        if (!active) return;
        if (err.error_code === 'TASK_NOT_FOUND' || err.code === 'TASK_NOT_FOUND') { setTask(null); setProgress(null); setError('任务记录已不存在，之前的内容仍可阅读。'); }
        else setPollError('进度连接中断，任务已保留，正在自动重试。');
      } finally { pending = false; }
    };
    poll(); const timer = setInterval(poll, 2000);
    return () => { active = false; clearInterval(timer); };
  }, [task, loading, reload]);

  const generate = async (kind, target) => {
    const owner = userId;
    setSubmitting(true); setError(''); setPollError('');
    try {
      const data = payload(await (kind === 'reading' ? briefingReportsApi.generateReading(target) : briefingReportsApi.generateModes({ mode: target, topic: topic.trim() })));
      if (userIdRef.current !== owner) return;
      setTask({ id: data.task_id, kind, sourceId: kind === 'reading' ? target : undefined, mode: kind === 'reading' ? undefined : target });
      setProgress({ progress: 0, progress_message: '已提交任务。' });
    } catch (err) { if (userIdRef.current === owner) setError(err.message || '生成未能启动，之前的内容已保留。'); }
    finally { if (userIdRef.current === owner) setSubmitting(false); }
  };
  const toggleQuote = id => setSavedQuotes(current => { const next = current.includes(id) ? current.filter(item => item !== id) : [...current, id]; localStorage.setItem(`${storagePrefix}:quotes`, JSON.stringify(next)); return next; });
  const copyQuote = async card => {
    const source = sources.find(item => item.id === card.source_id);
    const text = [card.quote, card.translation ? `译文：${card.translation}` : '', `${card.feed || source?.feed || ''} · ${card.source_title || source?.title || ''}${card.speaker ? ` · ${card.speaker}` : ''}${card.start != null ? ` · ${timeText(card.start)}` : ''}`].filter(Boolean).join('\n\n');
    try { await navigator.clipboard.writeText(text); setToast('原话和出处已复制'); } catch { setError('浏览器未允许复制，可以直接选中原话复制。'); }
  };
  const download = async () => {
    if (!report) return;
    const owner = userId;
    setDownloading(true); setError(''); setExportError('');
    try {
      const response = await briefingReportsApi.pdf(report.id, pages);
      if (userIdRef.current !== owner) return;
      const blob = response instanceof Blob ? response : new Blob([response], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob); const link = document.createElement('a');
      link.href = url; link.download = `PodMaster-${info.name}-${pages}页.pdf`;
      document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { const message = await errorText(err, 'PDF 导出失败，简报已保留。'); if (userIdRef.current === owner) { setError(message); setExportError(message); } }
    finally { if (userIdRef.current === owner) setDownloading(false); }
  };
  const retryReading = async () => { const owner = userId; setReadingLoading(true); setReadingError(''); try { const data = payload(await briefingReportsApi.reading(readingSource)); if (userIdRef.current === owner) setReadings(previous => ({ ...previous, [readingSource]: data })); } catch (err) { if (userIdRef.current === owner) setReadingError(err.message || '这期解读暂时无法读取。'); } finally { if (userIdRef.current === owner) setReadingLoading(false); } };
  const excerptProps = { sources, feeds, onRead: readEpisode, onListen, onSource: setSelection, savedQuotes, onToggleQuote: toggleQuote, onCopy: copyQuote, onTag: setSelectedTag, selectedTag, evidenceOpen, onEvidenceToggle: (id, open) => setEvidenceOpen(current => open ? current.includes(id) ? current : [...current, id] : current.filter(item => item !== id)) };
  const readingData = readingSource ? readings[readingSource] || { source: sources.find(source => source.id === readingSource) } : null;

  return <div ref={viewRef} className={`briefing-reports-view custom-scrollbar ${hasPlayer ? 'br-has-player' : ''}`}>
    <header className="br-page-header"><div className="br-page-heading"><button className="br-menu-button" onClick={onOpenMenu} aria-label="打开菜单"><Menu size={20} /></button>{readingSource ? <button className="br-back-button" onClick={() => setReadingSource(null)}><ArrowLeft size={17} />返回简报</button> : <div><h1>AI 简报</h1><p>{loading ? '正在读取简报' : `${sources.length} 期节目 · 五种内容模式`}</p></div>}</div></header>
    <main className="br-main">
      {!readingSource && <>
        <div className="br-toolbar br-modes-toolbar"><nav className="br-content-tabs" aria-label="五种内容模式">{modes.map(item => <button key={item.id} className={mode === item.id ? 'is-active' : ''} aria-pressed={mode === item.id} onClick={() => { setMode(item.id); viewRef.current?.scrollTo({ top: 0 }); }}>{item.name}</button>)}</nav><div className="br-toolbar-actions">
          <details className="br-scope"><summary>调整范围 <ChevronDown size={14} /></summary><section className="br-scope-panel"><label htmlFor="br-topic">自定义关注主题（可选）</label><input id="br-topic" value={topic} maxLength={120} onChange={event => setTopic(event.target.value)} placeholder="例如：AI 怎样改变工作" /><p>自定义主题在生成后应用。页面标签可立即筛选已有内容，风格只改变排版。</p><div className="br-scope-generate"><button className="br-button br-button-primary" disabled={working || !sources.length} onClick={event => { generate('modes', mode); event.currentTarget.closest('.br-scope').open = false; }}>{report ? '重新生成当前模式' : '生成当前模式'}</button><button className="br-button" disabled={working || !sources.length} onClick={event => { generate('modes', 'all'); event.currentTarget.closest('.br-scope').open = false; }}>生成所有模式</button></div><details className="br-source-list"><summary>查看 {sources.length} 期材料</summary>{sources.map(source => <button key={source.id} onClick={() => readEpisode(source.id)}><strong>{source.feed}</strong><span>{source.title}</span></button>)}</details></section></details>
          {report && <button className="br-button br-export" onClick={() => setPreview(true)}>导出 PDF</button>}
        </div></div>
        <div className="br-filter-bar"><nav className="br-topic-filters" aria-label="按主题筛选内容"><button className={!selectedTag ? 'is-active' : ''} aria-pressed={!selectedTag} onClick={() => setSelectedTag('')}>全部</button>{TOPIC_TAGS.map(tag => { const count = allItems.filter(card => card.topic_tags?.includes(tag) && (!savedOnly || isSaved(card))).length; return <button key={tag} className={selectedTag === tag ? 'is-active' : ''} aria-pressed={selectedTag === tag} onClick={() => setSelectedTag(selectedTag === tag ? '' : tag)}>{tag}<small>{count}</small></button>; })}</nav><div className="br-reading-tools"><button className={`br-saved-filter ${savedOnly ? 'is-active' : ''}`} aria-pressed={savedOnly} onClick={() => setSavedOnly(current => !current)}><Heart size={14} fill={savedOnly ? 'currentColor' : 'none'} />只看收藏</button><label className="br-style-control">风格<select value={layout} aria-label="阅读风格" onChange={event => setLayout(event.target.value)}>{LAYOUTS.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div></div>
        {report && <div className="br-filter-result" aria-live="polite"><span>{selectedTag ? `${selectedTag} · ` : ''}{savedOnly ? '收藏 · ' : ''}{filteredItems.length} 条内容 · {matchingSourceCount} 期节目{report.topic ? ` · 生成主题：${report.topic}` : ''}</span>{(selectedTag || savedOnly) && <button className="br-text-button" onClick={() => { setSelectedTag(''); setSavedOnly(false); }}>清除筛选</button>}</div>}
      </>}
      {error && <div className="br-notice br-notice-error" role="alert"><AlertCircle size={17} /><span>{error}</span><button className="br-text-button" onClick={() => { setError(''); reload().catch(err => setError(err.message || '重新加载失败。')); }}>重新加载</button><button className="br-icon-button" onClick={() => setError('')} aria-label="关闭提示"><X size={16} /></button></div>}
      {working && <div className="br-task-status" role="status"><div><Loader2 size={16} className="br-spinning" /><strong>{task?.kind === 'reading' ? '正在解读这期节目' : task?.mode === 'all' ? '正在生成五种内容模式' : `正在生成${modes.find(item => item.id === task?.mode)?.name || '简报'}`}</strong><span>{progress?.progress_message || progress?.message || '已提交任务'}</span></div><progress max="100" value={progress?.progress || 0} />{pollError && <p>{pollError}</p>}</div>}
      {readingSource ? <EpisodeReading data={readingData} loading={readingLoading} error={readingError} working={working} feeds={feeds} onGenerate={() => generate('reading', readingSource)} onSource={setSelection} onListen={onListen} onRetry={retryReading} /> : loading ? <div className="br-loading"><Loader2 size={20} className="br-spinning" />读取已保存的简报</div> : !report ? <div className="br-empty"><h2>还没有{info.name}</h2><p>{info.description || '从已有文稿整理，感兴趣再读整期。'}</p><button className="br-button br-button-primary" disabled={working || !sources.length} onClick={() => generate('modes', mode)}>生成当前模式</button><button className="br-button br-generate-all" disabled={working || !sources.length} onClick={() => generate('modes', 'all')}>生成所有模式</button></div> : <>
        {!['paper', 'newspaper'].includes(layout) && <header className="br-mode-intro"><h2>{info.name}</h2>{info.description && <p>{info.description}</p>}</header>}
        <section className={`br-quote-layout br-layout-${layout}`} aria-label={`${info.name} · ${LAYOUTS.find(item => item.id === layout).name}排版`}>
          {['paper', 'newspaper'].includes(layout) && <header className="br-paper-heading"><div><span>PodMaster · AI 简报</span><h2>{info.name}</h2></div><span>{dateText(report.generated_at)}</span></header>}
          {layout === 'newspaper' ? <div className="br-newspaper-items">{visibleItems.map(card => <Excerpt key={`${report.id}:${card.id}`} card={card} {...excerptProps} />)}</div> : visibleItems.map(card => <Excerpt key={`${report.id}:${card.id}`} card={card} {...excerptProps} />)}
          {['paper', 'newspaper'].includes(layout) && <footer className="br-paper-footer">{sources.length} 期文稿 · 当前 {visibleItems.length} 条，共 {filteredItems.length} 条 · 均可查看出处</footer>}
        </section>
        {filteredItems.length > 6 && <div className="br-expand-more"><button className="br-button" aria-expanded={showAll} onClick={() => setShowAll(current => !current)}>{showAll ? '收起，先看前 6 条' : `展开其余 ${filteredItems.length - 6} 条`}<ChevronDown size={14} /></button></div>}
        {!filteredItems.length && <div className="br-empty"><h2>{savedOnly ? '当前筛选中还没有收藏' : selectedTag ? `没有 ${selectedTag} 相关内容` : '这次没有符合主题的内容'}</h2><p>{savedOnly ? '点击内容下方的心形即可收藏。' : selectedTag ? '可切换主题标签或清除筛选。' : '可以调整关注主题后重新生成。'}</p></div>}
        <footer className="br-edition-footer"><span>生成于 {dateText(report.generated_at)}</span><button className="br-text-button" disabled={working} onClick={() => generate('modes', mode)}>重新生成当前模式</button></footer>
      </>}
      {!readingSource && prompt && <details className="br-generation-notes"><summary>生成说明 / 提示词 <ChevronDown size={15} /></summary><section><h3>输入内容</h3><p>{inputDescription}</p>{report?.prompt_user_template && <pre>{report.prompt_user_template}</pre>}<h3>{report ? '这份报告使用的提示词' : '当前模式的提示词'}</h3><pre>{prompt}</pre></section></details>}
    </main>
    {selection && <SourceDrawer selection={selection} onClose={closeSource} onOpenEpisode={onOpenEpisode} onListen={onListen} />}
    {preview && report && <PdfPreview report={report} pages={pages} onPagesChange={setPages} onClose={closePreview} onDownload={download} downloading={downloading} exportError={exportError} />}
    {toast && <div className="br-toast" role="status"><Check size={16} />{toast}</div>}
  </div>;
}
