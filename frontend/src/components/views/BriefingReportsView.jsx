import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  AlertCircle, ArrowLeft, Check, ChevronDown, Download, ExternalLink,
  Loader2, Menu, MoreHorizontal, X,
} from 'lucide-react';
import { briefingLabApi, briefingReportsApi } from '../../services/api';
import FeedImage from '../common/FeedImage';
import './briefing-reports.css';

const LAYOUTS = [
  { id: 'space', name: '留白', description: '一句主角，几句留给慢读' },
  { id: 'large', name: '大字', description: '原话铺开，一句一句读' },
  { id: 'list', name: '清单', description: '顺着读，快速挑想听的' },
  { id: 'columns', name: '双栏', description: '并排读，看看观点的不同' },
  { id: 'paper', name: '纸面', description: '一张可以带走的阅读页' },
];
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
function quotesIn(edition) { return (edition?.sections || []).flatMap(section => section.items || []).filter(item => item.kind === 'quote'); }
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

function Excerpt({ card, sources, feeds, onRead, onListen, onSource, savedQuotes, onToggleQuote, onCopy }) {
  const source = sources.find(item => item.id === card.source_id) || {};
  const episodeId = card.episode_id || source.episode_id;
  const episodeTitle = card.source_title || source.title;
  const saved = savedQuotes.includes(card.id);
  const listen = () => onListen({ ...card, episode_id: episodeId, original_url: source.original_url || source.url || source.link });
  return <article className="br-excerpt" data-quote-id={card.id}>
    <div className="br-excerpt-heading">{(card.brief || card.context) && <p className="br-brief">{card.brief || card.context}</p>}</div>
    <div className="br-excerpt-words"><OriginalQuote card={card} /></div>
    <footer className="br-excerpt-footer">
      <div className="br-source-identity"><Cover source={{ ...source, feed: card.feed || source.feed }} feeds={feeds} /><div className="br-source-info"><div className="br-source-byline"><strong>{card.feed || source.feed || '来源节目'}</strong>{card.speaker && <span>{card.speaker}</span>}</div>{episodeTitle && <span className="br-source-episode" title={episodeTitle}>{episodeTitle}</span>}</div></div>
      <div className="br-excerpt-actions">
        <button className="br-text-button" onClick={() => onRead(card.source_id)}>读这期</button>
        {episodeId && <button className="br-text-button br-listen" onClick={listen}>从 {timeText(card.start) || '开头'} 听</button>}
        <details className="br-more"><summary aria-label="更多原话操作" title="更多原话操作"><MoreHorizontal size={19} /></summary><div className="br-more-menu">
          {card.translation && <details className="br-inline-original"><summary>英文原话</summary><p lang="en">{card.quote}</p></details>}
          <button onClick={event => { onSource(card); event.currentTarget.closest('.br-more').open = false; }}>在文稿中查看</button>
          <button onClick={() => onCopy(card)}>复制原话与出处</button>
          <button onClick={() => onToggleQuote(card.id)}>{saved ? '取消收藏' : '收藏这句话'}{saved && <Check size={14} />}</button>
        </div></details>
      </div>
    </footer>
  </article>;
}

function CommonThreads({ threads, quotes, excerptProps, openThreads, onToggle }) {
  if (!threads?.length) return null;
  return <section className="br-threads" aria-label="节目中的共同话题">{threads.map((thread, index) => <details key={index} open={openThreads.includes(index)} onToggle={event => onToggle(index, event.currentTarget.open)}><summary><span className="br-thread-label">共同谈到 <small>AI 归纳</small></span><span>{thread.text}</span><ChevronDown size={15} /></summary><div className="br-thread-evidence">{thread.supporting_item_ids.map(id => quotes.find(card => card.id === id)).filter(Boolean).map(card => <Excerpt key={card.id} card={card} {...excerptProps} />)}</div></details>)}</section>;
}

function EpisodeReading({ data, loading, error, working, feeds, onGenerate, onSource, onListen, onRetry }) {
  const source = data?.source || {};
  const reading = data?.reading;
  return <article className="br-reading">
    <header className="br-reading-heading"><Cover source={source} feeds={feeds} large /><div><p>{source.feed}{source.duration > 0 ? ` · ${timeText(source.duration)}` : ''}</p><h1>{source.title || '正在读取节目'}</h1></div></header>
    {loading ? <div className="br-loading"><Loader2 size={18} className="br-spinning" />读取这期解读</div> : error ? <div className="br-notice br-notice-error" role="alert"><span>{error}</span><button className="br-text-button" onClick={onRetry}>重新加载</button></div> : !reading ? <section className="br-reading-empty"><h2>这期还没有单篇解读</h2><p>从已保存的文稿提炼少量要点，每个要点都附原话。</p><button className="br-button br-button-primary" disabled={working} onClick={onGenerate}>{working && <Loader2 size={15} className="br-spinning" />}生成这期解读</button><button className="br-text-button" onClick={() => onSource({ source_id: source.id, source_title: source.title, feed: source.feed, episode_id: source.episode_id })}>先读文稿</button></section> : <>
      <section className="br-reading-takeaway"><span className="br-reading-label">这期在说什么 · AI 解读</span><h2>{reading.takeaway}</h2></section>
      <section className="br-reading-points" aria-label="节目要点">{reading.points.map((point, index) => <details className="br-reading-point" key={index}><summary><div><h3>{point.title}</h3><p>{point.meaning}</p></div><span className="br-evidence-toggle">原话 <ChevronDown size={16} /></span></summary><div className="br-reading-evidence"><OriginalQuote card={point.quote} /><div className="br-reading-quote-actions">{point.quote.translation && <details className="br-inline-original"><summary>英文原话</summary><p lang="en">{point.quote.quote}</p></details>}<button className="br-text-button" onClick={() => onSource(point.quote)}>在文稿中查看</button>{source.episode_id && <button className="br-text-button" onClick={() => onListen({ ...point.quote, episode_id: source.episode_id, original_url: source.original_url || source.url || source.link })}>从 {timeText(point.quote.start) || '开头'} 听</button>}</div></div></details>)}</section>
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
    <div className="br-modal-heading"><div><h2 id="br-pdf-title">原话简报 · PDF 预览</h2><p>五种阅读排版共享这份精选；PDF 使用固定纸面版。</p></div><button className="br-icon-button" onClick={onClose} aria-label="关闭PDF预览"><X size={19} /></button></div>
    <div className="br-pdf-toolbar"><div className="br-segmented"><button className={pages === 1 ? 'is-active' : ''} onClick={() => onPagesChange(1)}>一页精选</button><button className={pages === 2 ? 'is-active' : ''} onClick={() => onPagesChange(2)}>两页报告</button></div><button className="br-button br-button-primary" disabled={downloading || !html} onClick={onDownload}>{downloading ? <Loader2 size={14} className="br-spinning" /> : <Download size={14} />}下载 PDF</button></div>
    {exportError && <div className="br-notice br-notice-error br-pdf-error" role="alert">{exportError}</div>}
    <div className="br-pdf-preview">{error ? <div className="br-notice br-notice-error" role="alert">{error}</div> : !html ? <div className="br-loading"><Loader2 size={18} className="br-spinning" />排版中</div> : <iframe title={`${pages}页原话简报预览`} srcDoc={html} sandbox="allow-popups allow-popups-to-escape-sandbox" />}</div>
  </section></div>, document.body);
}

export default function BriefingReportsView({ currentUser, feeds = [], onOpenEpisode, onListen, onOpenMenu, hasPlayer = false }) {
  const userId = currentUser?.id || currentUser?._id || 'guest';
  const storagePrefix = `podmaster_briefing_reading:${userId}`;
  const [layout, setLayout] = useState('space');
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
  const [openThreads, setOpenThreads] = useState([]);
  const viewRef = useRef(null);
  const userIdRef = useRef(userId);
  const readingScrollRef = useRef(0);
  userIdRef.current = userId;
  const edition = snapshot?.edition;
  const sources = edition?.sources || snapshot?.sources || [];
  const quotes = quotesIn(edition);
  const working = Boolean(task || submitting);
  const closeSource = useCallback(() => setSelection(null), []);
  const closePreview = useCallback(() => setPreview(false), []);
  const reload = useCallback(async () => { const data = payload(await briefingReportsApi.edition()); if (userIdRef.current === userId) setSnapshot(data); return data; }, [userId]);
  const readEpisode = sourceId => { readingScrollRef.current = viewRef.current?.scrollTop || 0; setReadingSource(sourceId); setReadingError(''); };
  useLayoutEffect(() => { viewRef.current?.scrollTo({ top: readingSource ? 0 : readingScrollRef.current }); }, [readingSource]);

  useEffect(() => {
    let active = true;
    readingScrollRef.current = 0;
    setLoading(true); setSnapshot(null); setReadingSource(null); setReadings({}); setError(''); setPreview(false); setSelection(null); setProgress(null); setPollError(''); setSubmitting(false); setReadingLoading(false); setDownloading(false); setExportError(''); setOpenThreads([]);
    const storedLayout = localStorage.getItem(`${storagePrefix}:layout`);
    setLayout(LAYOUTS.some(item => item.id === storedLayout) ? storedLayout : 'space');
    const savedTopic = readStored(sessionStorage, `${storagePrefix}:topic`, null);
    setTopic(savedTopic || '');
    setTask(readStored(sessionStorage, `${storagePrefix}:task`, null));
    setSavedQuotes(readStored(localStorage, `${storagePrefix}:quotes`, []));
    briefingReportsApi.edition().then(response => { if (active) { const data = payload(response); setSnapshot(data); if (savedTopic === null) setTopic(data.edition?.topic || ''); } }).catch(err => { if (active) setError(err.message || '简报暂时无法加载。'); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [storagePrefix]);
  useEffect(() => { if (!loading) localStorage.setItem(`${storagePrefix}:layout`, layout); }, [layout, loading, storagePrefix]);
  useEffect(() => { if (!loading) sessionStorage.setItem(`${storagePrefix}:topic`, JSON.stringify(topic)); }, [topic, loading, storagePrefix]);
  useEffect(() => {
    if (loading) return;
    if (task) sessionStorage.setItem(`${storagePrefix}:task`, JSON.stringify(task));
    else sessionStorage.removeItem(`${storagePrefix}:task`);
  }, [task, loading, storagePrefix]);
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(''), 3000); return () => clearTimeout(timer); }, [toast]);
  useEffect(() => { setOpenThreads([]); }, [edition?.id]);
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
          if (state.result?.edition) setSnapshot(previous => ({ ...previous, edition: state.result.edition }));
          if (state.result?.reading) { const reading = state.result.reading; setReadings(previous => ({ ...previous, [reading.source_id]: { ...previous[reading.source_id], reading, source: reading.source } })); }
          setTask(null); setProgress(null);
          if (task.kind === 'edition') { try { await reload(); } catch { if (active) setError('精选已生成，列表暂未刷新。请重新加载。'); } }
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

  const generate = async (kind, sourceId) => {
    const owner = userId;
    setSubmitting(true); setError(''); setPollError('');
    try {
      const data = payload(await (kind === 'reading' ? briefingReportsApi.generateReading(sourceId) : briefingReportsApi.generateEdition({ topic: topic.trim() })));
      if (userIdRef.current !== owner) return;
      setTask({ id: data.task_id, kind, sourceId });
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
    if (!edition) return;
    const owner = userId;
    setDownloading(true); setError(''); setExportError('');
    try {
      const response = await briefingReportsApi.pdf(edition.id, pages);
      if (userIdRef.current !== owner) return;
      const blob = response instanceof Blob ? response : new Blob([response], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob); const link = document.createElement('a');
      link.href = url; link.download = `PodMaster-原话简报-${pages}页.pdf`;
      document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { const message = await errorText(err, 'PDF 导出失败，简报已保留。'); if (userIdRef.current === owner) { setError(message); setExportError(message); } }
    finally { if (userIdRef.current === owner) setDownloading(false); }
  };
  const retryReading = async () => { const owner = userId; setReadingLoading(true); setReadingError(''); try { const data = payload(await briefingReportsApi.reading(readingSource)); if (userIdRef.current === owner) setReadings(previous => ({ ...previous, [readingSource]: data })); } catch (err) { if (userIdRef.current === owner) setReadingError(err.message || '这期解读暂时无法读取。'); } finally { if (userIdRef.current === owner) setReadingLoading(false); } };
  const excerptProps = { sources, feeds, onRead: readEpisode, onListen, onSource: setSelection, savedQuotes, onToggleQuote: toggleQuote, onCopy: copyQuote };
  const readingData = readingSource ? readings[readingSource] || { source: sources.find(source => source.id === readingSource) } : null;

  return <div ref={viewRef} className={`briefing-reports-view custom-scrollbar ${hasPlayer ? 'br-has-player' : ''}`}>
    <header className="br-page-header"><div className="br-page-heading"><button className="br-menu-button" onClick={onOpenMenu} aria-label="打开菜单"><Menu size={20} /></button>{readingSource ? <button className="br-back-button" onClick={() => setReadingSource(null)}><ArrowLeft size={17} />返回简报</button> : <div><h1>AI 简报</h1><p>{loading ? '正在读取精选' : `${sources.length} 期节目${edition ? ` · 精选 ${quotes.length} 句` : ' · 从原话开始'}`}</p></div>}</div></header>
    <main className="br-main">
      {!readingSource && <div className="br-toolbar"><nav className="br-layout-tabs" aria-label="五种阅读排版">{LAYOUTS.map(item => <button key={item.id} className={layout === item.id ? 'is-active' : ''} aria-pressed={layout === item.id} title={item.description} onClick={() => setLayout(item.id)}>{item.name}</button>)}</nav><div className="br-toolbar-actions">
        <details className="br-scope"><summary>调整范围 <ChevronDown size={14} /></summary><section className="br-scope-panel"><label htmlFor="br-topic">我关注的主题（可选）</label><input id="br-topic" value={topic} maxLength={120} onChange={event => setTopic(event.target.value)} placeholder="例如：AI 怎样改变工作" /><p>从已有文稿中挑少量原话。切换排版使用同一份内容。</p><button className="br-button br-button-primary" disabled={working || !sources.length} onClick={event => { generate('edition'); event.currentTarget.closest('.br-scope').open = false; }}>{edition ? '重新精选' : '生成简报'}</button><details className="br-source-list"><summary>查看 {sources.length} 期材料</summary>{sources.map(source => <button key={source.id} onClick={() => readEpisode(source.id)}><strong>{source.feed}</strong><span>{source.title}</span></button>)}</details></section></details>
        {edition && <button className="br-button br-export" onClick={() => setPreview(true)}>导出 PDF</button>}
      </div></div>}
      {error && <div className="br-notice br-notice-error" role="alert"><AlertCircle size={17} /><span>{error}</span><button className="br-text-button" onClick={() => { setError(''); reload().catch(err => setError(err.message || '重新加载失败。')); }}>重新加载</button><button className="br-icon-button" onClick={() => setError('')} aria-label="关闭提示"><X size={16} /></button></div>}
      {working && <div className="br-task-status" role="status"><div><Loader2 size={16} className="br-spinning" /><strong>{task?.kind === 'reading' ? '正在解读这期节目' : '正在精选原话'}</strong><span>{progress?.progress_message || progress?.message || '已提交任务'}</span></div><progress max="100" value={progress?.progress || 0} />{pollError && <p>{pollError}</p>}</div>}
      {readingSource ? <EpisodeReading data={readingData} loading={readingLoading} error={readingError} working={working} feeds={feeds} onGenerate={() => generate('reading', readingSource)} onSource={setSelection} onListen={onListen} onRetry={retryReading} /> : loading ? <div className="br-loading"><Loader2 size={20} className="br-spinning" />读取已保存的简报</div> : !edition ? <div className="br-empty"><h2>先挑几句值得听的原话</h2><p>从 {sources.length} 期文稿里精选，感兴趣再读整期。</p><button className="br-button br-button-primary" disabled={working || !sources.length} onClick={() => generate('edition')}>生成一份简报</button></div> : <>
        <CommonThreads threads={edition.threads} quotes={quotes} excerptProps={excerptProps} openThreads={openThreads} onToggle={(index, open) => setOpenThreads(current => open ? current.includes(index) ? current : [...current, index] : current.filter(item => item !== index))} />
        <section className={`br-quote-layout br-layout-${layout}`} aria-label={`${LAYOUTS.find(item => item.id === layout).name}排版`}>
          {layout === 'paper' && <header className="br-paper-heading"><span>PodMaster · 节目原话</span><span>{dateText(edition.generated_at)}</span></header>}
          {quotes.map(card => <Excerpt key={card.id} card={card} {...excerptProps} />)}
          {layout === 'paper' && <footer className="br-paper-footer">{sources.length} 期文稿 · {quotes.length} 句精选 · 每句话都可以回听</footer>}
        </section>
        {!quotes.length && <div className="br-empty"><h2>这次没有符合主题的原话</h2><p>可以调整关注主题后重新精选。</p></div>}
        <footer className="br-edition-footer"><span>精选于 {dateText(edition.generated_at)}{edition.topic ? ` · ${edition.topic}` : ''}</span><button className="br-text-button" disabled={working} onClick={() => generate('edition')}>重新精选</button></footer>
      </>}
    </main>
    {selection && <SourceDrawer selection={selection} onClose={closeSource} onOpenEpisode={onOpenEpisode} onListen={onListen} />}
    {preview && edition && <PdfPreview report={edition} pages={pages} onPagesChange={setPages} onClose={closePreview} onDownload={download} downloading={downloading} exportError={exportError} />}
    {toast && <div className="br-toast" role="status"><Check size={16} />{toast}</div>}
  </div>;
}
