import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  AlertCircle, BookOpen, Check, ChevronDown, Copy, Download, ExternalLink,
  FileText, Globe, Headphones, Layers, Loader2, Menu, Quote, RefreshCw, Search,
  Sparkles, Star, X,
} from 'lucide-react';
import { briefingLabApi, briefingReportsApi } from '../../services/api';
import FeedImage from '../common/FeedImage';
import './briefing-reports.css';

const VARIANTS = [
  { id: 'overview', name: '本期速览', description: '新词、原话与资料，一起看', icon: Layers },
  { id: 'episodes', name: '逐期摘录', description: '按节目看这期说了什么', icon: Headphones },
  { id: 'concepts', name: '本期新词', description: '白话解释，以及节目中的用法', icon: Sparkles },
  { id: 'quotes', name: '金句摘录', description: '保留原话，也保留上下文', icon: Quote },
  { id: 'resources', name: '提到的资料', description: '书、文章、论文、工具与网站', icon: BookOpen },
];
const INTERESTS = [
  { id: 'concepts', name: '新词' }, { id: 'quotes', name: '金句' },
  { id: 'resources', name: '资料' }, { id: 'backgrounds', name: '人物背景' },
];
const KIND_LABELS = { concept: '术语', quote: '原话', resource: '资料', background: '背景', episode: '节目' };
const RESOURCE_LABELS = { book: '书', article: '文章', paper: '论文', tool: '工具', website: '网站', report: '报告', podcast: '播客', other: '资料' };
const RELATION_LABELS = { mentioned: '节目提到', recommended: '嘉宾推荐', supplemental: '补充阅读', background: '补充背景', external: '补充背景', episode_mention: '节目提到', explicit_recommendation: '嘉宾推荐', further_reading: '补充阅读' };
const WEB_LABELS = {
  disabled: '仅使用节目文稿', live_search: '已加入本次检索背景',
  saved_primary_source_notes: '背景来自已有检索资料', unavailable: '本次未取得补充背景',
};
const DEFAULT_INTERESTS = ['concepts', 'quotes', 'resources'];

function payload(response) { return response?.data ?? response; }
function timeText(value) {
  if (value == null || !Number.isFinite(Number(value))) return '';
  const seconds = Math.floor(Number(value));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds % 3600 / 60);
  return `${hours ? `${hours}:` : ''}${hours ? String(minutes).padStart(2, '0') : minutes}:${String(seconds % 60).padStart(2, '0')}`;
}
function dateText(value) {
  return value ? new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Hong_Kong', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '';
}
function readStored(key, fallback) {
  const stored = sessionStorage.getItem(key);
  if (!stored) return fallback;
  try { return JSON.parse(stored); } catch { sessionStorage.removeItem(key); return fallback; }
}
function usableUrl(url) { return typeof url === 'string' && /^https?:\/\//i.test(url) ? url : null; }
function cardsIn(report) { return (report?.sections || []).flatMap(section => section.items || []); }
function latestReports(reports) {
  return (reports || []).reduce((all, report) => {
    if (!all[report.variant] || new Date(report.generated_at) >= new Date(all[report.variant].generated_at)) all[report.variant] = report;
    return all;
  }, {});
}
async function errorText(error, fallback) {
  if (error instanceof Blob) {
    const raw = await error.text();
    try { return JSON.parse(raw).message || fallback; } catch { return fallback; }
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
      if (!elements.length) return;
      const first = elements[0];
      const last = elements.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); before?.focus(); };
  }, [ref, onClose]);
}

function Cover({ source, feeds, size = 'small' }) {
  const feed = feeds.find(item => item.id === source?.feed_id || item.title === source?.feed);
  const image = usableUrl(source?.image || source?.image_url || feed?.image_url || feed?.image);
  return image ? <FeedImage feed={{ ...feed, image, title: source?.feed || feed?.title || '' }} className={`br-cover br-cover-${size}`} /> : <span className={`br-cover br-cover-${size} br-cover-fallback`} aria-hidden="true"><Headphones size={size === 'large' ? 24 : 15} /></span>;
}

function SourceLine({ card, sources, feeds, onOpenEpisode, onListen, onSource, compact = false }) {
  const source = sources.find(item => item.id === card.source_id) || {};
  const feedName = card.feed || source.feed;
  const episodeTitle = card.source_title || source.title;
  const episodeId = card.episode_id || source.episode_id;
  const time = timeText(card.start);
  const shortClip = source.duration > 0 && source.duration <= 120;
  return <div className={`br-source ${compact ? 'br-source-compact' : ''}`}>
    <div className="br-source-identity"><Cover source={{ ...source, feed: feedName }} feeds={feeds} /><div><strong>{feedName || '来源节目'}{source.duration > 0 && <small>{shortClip ? '短片 · ' : ''}{timeText(source.duration)}</small>}</strong><span>{episodeTitle}{card.speaker ? ` · ${card.speaker}` : ''}</span></div></div>
    <div className="br-source-actions">
      {episodeId && <button className="br-text-button" onClick={() => onListen({ ...card, episode_id: episodeId, original_url: source.original_url || source.url || source.link })} title={time ? `从 ${time} 回听` : '收听这期节目'}><Headphones size={13} />{time ? `从 ${time} 听` : '收听'}</button>}
      {episodeId && <button className="br-text-button" onClick={() => onOpenEpisode(episodeId)} title="切换到传统模式并打开这期节目">打开节目</button>}
      {card.source_id && <button className="br-text-button" onClick={() => onSource(card)}>查看原文</button>}
      {!episodeId && usableUrl(card.url || source.original_url) && <a className="br-text-button" href={card.url || source.original_url} target="_blank" rel="noopener noreferrer">打开原文<ExternalLink size={12} /></a>}
    </div>
  </div>;
}

function QuoteText({ card, showContext = true }) {
  return <>
    {card.translation ? <><span className="br-field-label">中文译文</span><blockquote>{card.translation}</blockquote>{card.quote && <details className="br-original-quote"><summary>查看原文 <ChevronDown size={12} /></summary><blockquote lang="en">{card.quote}</blockquote></details>}</> : card.quote ? <blockquote>{card.quote}</blockquote> : null}
    {showContext && card.context && <p className="br-context"><span>当时在谈</span>{card.context}</p>}
  </>;
}

function ContentCard({ card, onSource, sources, feeds, onOpenEpisode, onListen, savedQuotes, onToggleQuote, copyQuote, compact = false }) {
  const kind = card.kind;
  const resourceKind = RESOURCE_LABELS[card.resource_kind] || card.resource_kind;
  const relation = RELATION_LABELS[card.relation] || card.relation || '节目提到';
  const saved = savedQuotes.includes(card.id);
  return <article className={`br-content-card br-kind-${kind} ${compact ? 'br-card-compact' : ''}`}>
    <div className="br-card-topline"><span className="br-kind-label">{kind === 'resource' ? resourceKind || '资料' : kind === 'background' ? card.relation === 'external' ? '外部背景' : '文稿背景' : KIND_LABELS[kind] || '摘录'}</span>{kind === 'resource' && <span className="br-relation-label">{relation}</span>}{kind === 'quote' && <div className="br-quote-actions"><button className={`br-icon-button ${saved ? 'is-saved' : ''}`} aria-label={saved ? '取消收藏原话' : '收藏原话'} title={saved ? '已收藏在此浏览器' : '收藏到此浏览器'} onClick={() => onToggleQuote(card.id)}><Star size={14} fill={saved ? 'currentColor' : 'none'} /></button><button className="br-icon-button" aria-label="复制原话" title="复制原话和出处" onClick={() => copyQuote(card)}><Copy size={14} /></button></div>}</div>
    <h3>{card.title}</h3>
    {kind === 'concept' && card.original_term && !card.title?.toLowerCase().includes(card.original_term.toLowerCase()) && <p className="br-original-term">{card.original_term}</p>}
    {kind === 'concept' ? <><p className="br-card-text">{card.text}</p>{card.context && <p className="br-context"><span>这期怎么用</span>{card.context}</p>}{card.quote && <details className="br-original-quote"><summary>节目原话 <ChevronDown size={12} /></summary><blockquote>{card.quote}</blockquote></details>}</> : kind === 'quote' ? <QuoteText card={card} /> : <><p className="br-card-text">{card.text}</p>{card.context && <p className="br-context"><span>{kind === 'resource' ? '提到它是因为' : '相关背景'}</span>{card.context}</p>}{card.quote && <details className="br-original-quote"><summary>提及原话 <ChevronDown size={12} /></summary><blockquote>{card.quote}</blockquote></details>}</>}
    {kind === 'resource' && (usableUrl(card.url) ? <a className="br-resource-link" href={card.url} target="_blank" rel="noopener noreferrer"><ExternalLink size={13} />打开资料</a> : <span className="br-link-pending">资料原站链接待确认</span>)}
    {kind === 'background' && usableUrl(card.url) && <><a className="br-resource-link" href={card.url} target="_blank" rel="noopener noreferrer"><Globe size={13} />{card.publisher || card.background_source || '查看背景来源'}</a>{card.accessed_at && <span className="br-link-pending">查阅于 {dateText(card.accessed_at)}</span>}</>}
    <SourceLine card={card} sources={sources} feeds={feeds} onOpenEpisode={onOpenEpisode} onListen={onListen} onSource={onSource} compact={compact} />
    {card.also_in?.length > 0 && <div className="br-also-in">还出现在{card.also_in.map((item, index) => <button key={index} onClick={() => onSource({ ...card, ...item })}>{item.feed || sources.find(source => source.id === item.source_id)?.feed || '其他节目'}</button>)}</div>}
  </article>;
}

function OverviewReport({ report, cardProps }) {
  return <div className="br-overview-layout">{(report.sections || []).map(section => <section className={`br-report-section br-section-${section.kind || section.id}`} key={section.id}>
    <div className="br-section-heading"><h2>{section.title}</h2><span>{section.items?.length || 0} 条</span></div>
    <div className="br-card-grid">{(section.items || []).map(card => <ContentCard key={card.id} card={card} compact {...cardProps} />)}</div>
  </section>)}</div>;
}

function EpisodeReport({ report, cardProps }) {
  return <><div className="br-episodes-layout">{cardsIn(report).filter(card => card.kind === 'episode').map(card => {
    const source = cardProps.sources.find(item => item.id === card.source_id) || {};
    return <article className="br-episode-card" key={card.id}>
      <header className="br-episode-heading"><Cover source={{ ...source, feed: card.feed }} feeds={cardProps.feeds} size="large" /><div><span className="br-kind-label">{card.feed || source.feed}{source.duration > 0 && <small className="br-duration">{source.duration <= 120 ? '短片 · ' : ''}{timeText(source.duration)}</small>}</span><h2>{card.source_title || card.title}</h2>{card.speaker && <p>{card.speaker}</p>}</div></header>
      {card.text && <p className="br-episode-about">{card.text}</p>}
      <div className="br-episode-excerpts">{(card.children || []).map(child => <div className={`br-episode-excerpt br-kind-${child.kind}`} key={child.id}><span className="br-field-label">{KIND_LABELS[child.kind] || '摘录'}</span><h3>{child.title}</h3>{child.kind === 'quote' ? <QuoteText card={child} /> : <><p>{child.text}</p>{child.context && <p className="br-context">{child.context}</p>}{child.kind === 'resource' && usableUrl(child.url) && <a className="br-resource-link" href={child.url} target="_blank" rel="noopener noreferrer"><ExternalLink size={12} />打开资料</a>}</>}{child.start != null && <button className="br-text-button" onClick={() => cardProps.onListen({ ...child, episode_id: child.episode_id || card.episode_id || source.episode_id, original_url: source.original_url || source.url || source.link })}><Headphones size={12} />{timeText(child.start)} 回听</button>}<button className="br-text-button" onClick={() => cardProps.onSource(child)}>原文</button></div>)}</div>
      <SourceLine card={card} {...cardProps} />
    </article>;
  })}</div>{(report.sections || []).filter(section => section.kind !== 'episode').map(section => <section className="br-report-section br-extra-section" key={section.id}><div className="br-section-heading"><h2>{section.title}</h2><span>{section.items?.length || 0} 条</span></div><div className="br-card-grid">{(section.items || []).map(card => <ContentCard key={card.id} card={card} {...cardProps} />)}</div></section>)}</>;
}

function ConceptsReport({ report, cardProps }) {
  return <>{(report.sections || []).map(section => <section className="br-report-section" key={section.id}>{section.kind !== 'concept' && <div className="br-section-heading"><h2>{section.title}</h2><span>{section.items?.length || 0} 条</span></div>}<div className={section.kind === 'concept' ? 'br-concepts-layout' : 'br-card-grid'}>{(section.items || []).map(card => <ContentCard key={card.id} card={card} {...cardProps} />)}</div></section>)}</>;
}
function QuotesReport({ report, cardProps }) {
  return <>{(report.sections || []).map(section => <section className="br-report-section" key={section.id}>{section.kind !== 'quote' && <div className="br-section-heading"><h2>{section.title}</h2><span>{section.items?.length || 0} 条</span></div>}<div className={section.kind === 'quote' ? 'br-quotes-layout' : 'br-card-grid'}>{(section.items || []).map(card => <ContentCard key={card.id} card={card} {...cardProps} />)}</div></section>)}</>;
}
function ResourcesReport({ report, cardProps }) {
  return <div className="br-resources-layout">{(report.sections || []).map(section => <section className="br-report-section" key={section.id}><div className="br-section-heading"><h2>{section.title}</h2><span>{section.items?.length || 0} 条</span></div><div className="br-resource-grid">{(section.items || []).map(card => <ContentCard key={card.id} card={card} {...cardProps} />)}</div></section>)}</div>;
}
const REPORT_COMPONENTS = { overview: OverviewReport, episodes: EpisodeReport, concepts: ConceptsReport, quotes: QuotesReport, resources: ResourcesReport };

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
  useEffect(() => {
    if (source) bodyRef.current?.querySelector('.br-highlighted')?.scrollIntoView({ block: 'center' });
  }, [source, selection]);
  const quote = selection.quote;
  const segments = source?.segments || [];
  const offset = quote && source?.full_text ? source.full_text.indexOf(quote) : -1;
  const highlightIndex = quote ? segments.findIndex(segment => segment.text?.includes(quote)) : -1;
  const timedHighlight = highlightIndex >= 0 ? highlightIndex : selection.start != null ? segments.findIndex(segment => Number(segment.start ?? segment.time ?? 0) <= selection.start && Number(segment.end ?? Number(segment.start ?? segment.time ?? 0) + 30) >= selection.start) : -1;
  return createPortal(<div className="br-modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <aside className="br-source-drawer" ref={ref} role="dialog" aria-modal="true" aria-labelledby="br-source-title">
      <div className="br-modal-heading"><div><span className="br-field-label">{source?.feed || selection.feed || '节目文稿'}</span><h2 id="br-source-title">{source?.title || selection.source_title || '正在读取原文'}</h2></div><button className="br-icon-button" onClick={onClose} aria-label="关闭原文"><X size={19} /></button></div>
      <div className="br-drawer-toolbar">{(selection.episode_id || source?.episode_id) && <><button className="br-button" onClick={() => { onClose(); onOpenEpisode(selection.episode_id || source.episode_id); }}>打开节目</button><button className="br-button" onClick={() => onListen({ ...selection, episode_id: selection.episode_id || source.episode_id, original_url: source?.original_url })}><Headphones size={14} />{selection.start != null ? `从 ${timeText(selection.start)} 听` : '收听节目'}</button></>}{source && <span>{source.char_count?.toLocaleString()} 字符</span>}</div>
      <div className="br-source-body custom-scrollbar" ref={bodyRef}>
        {error ? <div className="br-notice br-notice-error"><AlertCircle size={16} />{error}</div> : !source ? <div className="br-loading"><Loader2 size={18} className="br-spinning" />读取已保存文稿</div> : <>
          {quote && <div className="br-selected-quote"><strong>这条摘录的原文{selection.start != null ? ` · ${timeText(selection.start)}` : ''}</strong><p>{quote}</p></div>}
          {segments.length ? segments.map((segment, index) => {
            const quoteIndex = quote ? segment.text?.indexOf(quote) : -1;
            return <div className={`br-transcript-segment ${index === timedHighlight ? 'br-highlighted' : ''}`} key={index}><span>{timeText(segment.start ?? segment.time)}{segment.speaker ? ` · ${segment.speaker}` : ''}</span><p>{quoteIndex >= 0 ? <>{segment.text.slice(0, quoteIndex)}<mark>{quote}</mark>{segment.text.slice(quoteIndex + quote.length)}</> : segment.text}</p></div>;
          }) : <div className="br-full-text">{offset >= 0 ? <>{source.full_text.slice(0, offset)}<mark className="br-highlighted">{quote}</mark>{source.full_text.slice(offset + quote.length)}</> : source.full_text}</div>}
        </>}
      </div>
    </aside>
  </div>, document.body);
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
    <div className="br-modal-heading"><div><h2 id="br-pdf-title">{report.title} · PDF 预览</h2><p>导出这份已保存的报告，内容与预览一致。</p></div><button className="br-icon-button" onClick={onClose} aria-label="关闭PDF预览"><X size={19} /></button></div>
    <div className="br-pdf-toolbar"><div className="br-segmented"><button className={pages === 1 ? 'is-active' : ''} onClick={() => onPagesChange(1)}>一页精选</button><button className={pages === 2 ? 'is-active' : ''} onClick={() => onPagesChange(2)}>两页报告</button></div><button className="br-button br-button-primary" disabled={downloading || !html} onClick={onDownload}>{downloading ? <Loader2 size={14} className="br-spinning" /> : <Download size={14} />}下载 PDF</button></div>
    {exportError && <div className="br-notice br-notice-error br-pdf-error" role="alert"><AlertCircle size={16} />{exportError}</div>}
    <div className="br-pdf-preview">{error ? <div className="br-notice br-notice-error"><AlertCircle size={16} />{error}</div> : !html ? <div className="br-loading"><Loader2 size={18} className="br-spinning" />排版中</div> : <iframe title={`${report.title} ${pages}页报告预览`} srcDoc={html} sandbox="allow-popups allow-popups-to-escape-sandbox" />}</div>
  </section></div>, document.body);
}

export default function BriefingReportsView({ currentUser, feeds = [], onOpenEpisode, onListen, onOpenMenu, hasPlayer = false }) {
  const userId = currentUser?.id || currentUser?._id || 'guest';
  const storagePrefix = `podmaster_briefing_reports:${userId}`;
  const initialDraft = readStored(`${storagePrefix}:draft`, { topic: '', interests: DEFAULT_INTERESTS, webEnabled: false });
  const hadDraftRef = useRef(Boolean(sessionStorage.getItem(`${storagePrefix}:draft`)));
  const [variant, setVariant] = useState(() => localStorage.getItem(`${storagePrefix}:variant`) || 'overview');
  const [topic, setTopic] = useState(initialDraft.topic);
  const [interests, setInterests] = useState(initialDraft.interests);
  const [webEnabled, setWebEnabled] = useState(initialDraft.webEnabled);
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [task, setTask] = useState(() => readStored(`${storagePrefix}:task`, null));
  const [progress, setProgress] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [pollError, setPollError] = useState('');
  const [selection, setSelection] = useState(null);
  const [preview, setPreview] = useState(false);
  const [pages, setPages] = useState(1);
  const [downloading, setDownloading] = useState(false);
  const [exportError, setExportError] = useState('');
  const [showSources, setShowSources] = useState(false);
  const [toast, setToast] = useState('');
  const [savedQuotes, setSavedQuotes] = useState(() => {
    const raw = localStorage.getItem(`${storagePrefix}:quotes`);
    if (!raw) return [];
    try { return JSON.parse(raw); } catch { return []; }
  });
  const latest = useMemo(() => latestReports(snapshot?.reports), [snapshot?.reports]);
  const report = latest[variant];
  const settingsChanged = report && (topic.trim() !== report.topic || JSON.stringify([...interests].sort()) !== JSON.stringify([...report.interests].sort()) || webEnabled !== (report.web_mode !== 'disabled'));
  const sources = report?.sources || snapshot?.corpus?.sources || [];
  const sourceCount = snapshot?.corpus?.sources?.length || 0;
  const characters = snapshot?.corpus?.characters || snapshot?.corpus?.char_count;
  const info = VARIANTS.find(item => item.id === variant) || VARIANTS[0];
  const ReportComponent = REPORT_COMPONENTS[info.id];
  const working = Boolean(task || submitting);
  const closeSource = useCallback(() => setSelection(null), []);
  const closePreview = useCallback(() => setPreview(false), []);
  const onSource = useCallback(card => setSelection(card), []);
  const reload = useCallback(async () => {
    const data = payload(await briefingReportsApi.snapshot());
    setSnapshot(data);
    return data;
  }, []);

  useEffect(() => {
    let active = true;
    briefingReportsApi.snapshot().then(response => {
      if (!active) return;
      const data = payload(response);
      setSnapshot(data);
      if (!hadDraftRef.current) {
        const saved = latestReports(data.reports || [])[variant];
        if (saved) {
          setTopic(saved.topic);
          setInterests(saved.interests);
          setWebEnabled(saved.web_mode !== 'disabled');
        }
        hadDraftRef.current = true;
      }
    }).catch(err => { if (active) setError(err.message || '简报暂时无法加载。'); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [userId]);
  useEffect(() => { sessionStorage.setItem(`${storagePrefix}:draft`, JSON.stringify({ topic, interests, webEnabled })); }, [topic, interests, webEnabled, storagePrefix]);
  useEffect(() => { localStorage.setItem(`${storagePrefix}:variant`, variant); }, [variant, storagePrefix]);
  useEffect(() => {
    if (task) sessionStorage.setItem(`${storagePrefix}:task`, JSON.stringify(task));
    else sessionStorage.removeItem(`${storagePrefix}:task`);
  }, [task, storagePrefix]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(''), 3000);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    if (!task) return;
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
          const generated = Array.isArray(state.result) ? state.result : state.result?.reports || (state.result?.variant ? [state.result] : []);
          if (generated.length) setSnapshot(previous => ({ ...previous, reports: [...(previous?.reports || []), ...generated] }));
          setTask(null); setProgress(null);
          try { await reload(); } catch { setError('报告已生成，列表刷新暂时失败。可以重新加载。'); }
        } else if (['failed', 'cancelled'].includes(state.status)) {
          setError(state.error || '本次生成未完成，之前的报告仍可阅读。');
          setTask(null); setProgress(null);
        }
      } catch (err) {
        if (!active) return;
        if (err.error_code === 'TASK_NOT_FOUND' || err.code === 'TASK_NOT_FOUND') { setTask(null); setProgress(null); setError('任务记录已不存在，之前的报告仍可阅读。'); }
        else setPollError('进度连接暂时中断，任务记录已保留；正在自动重试。');
      } finally { pending = false; }
    };
    poll();
    const timer = setInterval(poll, 2000);
    return () => { active = false; clearInterval(timer); };
  }, [task, reload]);

  const generate = async selected => {
    setSubmitting(true); setError(''); setPollError('');
    try {
      const data = payload(await briefingReportsApi.generate({ variant: selected, topic: topic.trim(), interests, web_enabled: webEnabled }));
      setTask({ id: data.task_id, variant: selected });
      setProgress({ progress: 0, progress_message: '已提交，正在整理节目文稿。' });
    } catch (err) { setError(err.message || '生成未能启动，之前的报告已保留。'); }
    finally { setSubmitting(false); }
  };
  const toggleInterest = id => setInterests(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]);
  const toggleQuote = id => setSavedQuotes(current => {
    const next = current.includes(id) ? current.filter(item => item !== id) : [...current, id];
    localStorage.setItem(`${storagePrefix}:quotes`, JSON.stringify(next));
    return next;
  });
  const copyQuote = async card => {
    const source = sources.find(item => item.id === card.source_id);
    const text = [card.quote, card.translation ? `中文译文：${card.translation}` : '', `${card.feed || source?.feed || ''} · ${card.source_title || source?.title || ''}${card.speaker ? ` · ${card.speaker}` : ''}${card.start != null ? ` · ${timeText(card.start)}` : ''}`].filter(Boolean).join('\n\n');
    try { await navigator.clipboard.writeText(text); setToast('原话和出处已复制'); } catch { setError('浏览器未允许复制，可以直接选中原话复制。'); }
  };
  const download = async () => {
    if (!report) return;
    setDownloading(true); setError(''); setExportError('');
    try {
      const response = await briefingReportsApi.pdf(report.id, pages);
      const blob = response instanceof Blob ? response : new Blob([response], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      const date = new Date(report.generated_at).toLocaleDateString('sv-SE', { timeZone: 'Asia/Hong_Kong' });
      link.href = url; link.download = `PodMaster-${info.name}-${date}-${pages}页.pdf`;
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { const message = await errorText(err, 'PDF 导出失败，报告内容已保留。'); setError(message); setExportError(message); }
    finally { setDownloading(false); }
  };
  const cardProps = { sources, feeds, onOpenEpisode, onListen, onSource, savedQuotes, onToggleQuote: toggleQuote, copyQuote };
  const searchAvailable = Boolean(snapshot?.diagnostics?.search_available);
  return <div className={`briefing-reports-view custom-scrollbar ${hasPlayer ? 'br-has-player' : ''}`}>
    <header className="br-page-header"><div className="br-page-heading"><button className="br-menu-button" onClick={onOpenMenu} aria-label="打开菜单"><Menu size={18} /></button><div><h1>AI 简报</h1><p>把关注的节目整理成新词、原话和资料，随时回听。</p></div></div><button className="br-icon-button" aria-label="刷新简报" title="刷新简报" disabled={loading} onClick={() => { setError(''); reload().catch(err => setError(err.message || '刷新失败。')); }}><RefreshCw size={16} className={loading ? 'br-spinning' : ''} /></button></header>
    <div className="br-main">
      <section className="br-controls" aria-label="简报范围与关注项">
        <div className="br-scope-line"><span className="br-scope-dot" /><strong>{sourceCount ? `最近 ${sourceCount} 篇有文稿的节目` : '有文稿的节目'}</strong>{characters > 0 && <span>{Number(characters).toLocaleString()} 字符</span>}<button className="br-text-button" onClick={() => setShowSources(current => !current)} aria-expanded={showSources}>{showSources ? '收起材料' : '查看材料'}<ChevronDown size={13} className={showSources ? 'br-flipped' : ''} /></button></div>
        <div className="br-control-row"><label className="br-topic-input"><Search size={15} /><input value={topic} maxLength={120} onChange={event => setTopic(event.target.value)} placeholder="主题关键词（可选，如商业、历史）" aria-label="主题关键词" /></label><div className="br-interests"><span>关注</span>{INTERESTS.map(interest => <button key={interest.id} className={`br-interest ${interests.includes(interest.id) ? 'is-active' : ''}`} aria-pressed={interests.includes(interest.id)} onClick={() => toggleInterest(interest.id)}>{interests.includes(interest.id) && <Check size={11} />}{interest.name}</button>)}</div></div>
        <div className="br-control-bottom"><label className="br-web-toggle"><input type="checkbox" checked={webEnabled} onChange={event => { setWebEnabled(event.target.checked); if (event.target.checked) setInterests(current => current.includes('backgrounds') ? current : [...current, 'backgrounds']); }} /><Globe size={13} />补充背景</label><span className="br-search-note">{webEnabled ? searchAvailable ? '按节目中的人物与资料检索' : '使用已有检索资料；当前未配置实时搜索' : '依据文稿整理，补充背景可按需开启'}</span><div className="br-generate-actions"><button className="br-button" disabled={working || !sourceCount || !interests.length} onClick={() => generate('all')}>生成全部版本</button><button className="br-button br-button-primary" disabled={working || !sourceCount || !interests.length} onClick={() => generate(variant)}>{working ? <Loader2 size={14} className="br-spinning" /> : <Sparkles size={14} />}生成当前版</button></div></div>
        {!interests.length && <p className="br-inline-warning">至少选择一项关注内容。</p>}
        {settingsChanged && <p className="br-inline-warning">当前显示已保存的报告；新的主题和关注项将在生成后应用。</p>}
      </section>
      {showSources && <section className="br-materials" aria-label="本次分析材料"><div className="br-section-heading"><h2>本次文稿</h2><span>点击查看完整内容</span></div><div className="br-materials-grid">{(snapshot?.corpus?.sources || []).map(source => <button className="br-material" key={source.id} onClick={() => onSource({ source_id: source.id, source_title: source.title, feed: source.feed, episode_id: source.episode_id })}><Cover source={source} feeds={feeds} /><div><strong>{source.feed}</strong><span>{source.title}</span></div><FileText size={14} /></button>)}</div></section>}
      <nav className="br-variant-tabs" aria-label="五种简报版本">{VARIANTS.map(item => { const Icon = item.icon; return <button key={item.id} className={variant === item.id ? 'is-active' : ''} aria-pressed={variant === item.id} onClick={() => { setVariant(item.id); setPages(item.id === 'episodes' ? 2 : 1); }}><Icon size={16} /><span>{item.name}</span>{latest[item.id] && <span className="br-tab-ready" aria-label="已有报告" />}</button>; })}</nav>
      {error && <div className="br-notice br-notice-error" role="alert"><AlertCircle size={16} /><span>{error}</span><button className="br-text-button" onClick={() => { setError(''); reload().catch(err => setError(err.message || '重新加载失败。')); }}>重新加载</button><button className="br-icon-button" onClick={() => setError('')} aria-label="关闭提示"><X size={14} /></button></div>}
      {working && <div className="br-task-status" role="status"><div><Loader2 size={15} className="br-spinning" /><strong>{task?.variant === 'all' ? '正在生成五种版本' : `正在生成${VARIANTS.find(item => item.id === task?.variant)?.name || '报告'}`}</strong><span>{progress?.progress_message || progress?.message || '已提交任务'}</span>{progress?.progress != null && <span>{Math.round(progress.progress)}%</span>}</div><progress max="100" value={progress?.progress || 0} />{pollError && <p>{pollError}</p>}</div>}
      <section className={`br-report-area br-report-${variant}`} aria-label={info.name}>
        <div className="br-report-heading"><div><h2>{info.name}</h2><p>{info.description}{report?.topic ? ` · 主题：${report.topic}` : ''}</p></div>{report && <div className="br-export-actions"><div className="br-segmented"><button className={pages === 1 ? 'is-active' : ''} onClick={() => setPages(1)}>一页</button><button className={pages === 2 ? 'is-active' : ''} onClick={() => setPages(2)}>两页</button></div><button className="br-button" onClick={() => setPreview(true)}><FileText size={14} />预览</button><button className="br-button" onClick={download} disabled={downloading}>{downloading ? <Loader2 size={14} className="br-spinning" /> : <Download size={14} />}PDF</button></div>}</div>
        {loading ? <div className="br-loading"><Loader2 size={18} className="br-spinning" />读取已保存的简报</div> : !report ? <div className="br-empty"><FileText size={24} /><h3>还没有{info.name}报告</h3><p>选择关注内容后，点击“生成当前版”。五个版本使用同一批节目文稿。</p></div> : <>
          <ReportComponent report={report} cardProps={cardProps} />
          {!cardsIn(report).length && <div className="br-empty"><BookOpen size={23} /><h3>本次材料没有符合条件的摘录</h3><p>{['concepts', 'quotes', 'resources'].includes(variant) && !report.interests.includes(variant) ? `这份报告没有选择“${INTERESTS.find(item => item.id === variant).name}”，开启该关注项后可以重新生成。` : '可以调整主题或关注项，不会为填满版式补造内容。'}</p></div>}
          <footer className="br-report-footer"><span>生成于 {dateText(report.generated_at)}</span><span>{WEB_LABELS[report.web_mode] || '来源可在原文中查看'}</span><span>{report.coverage?.sources || sources.length} 篇材料</span></footer>
        </>}
      </section>
    </div>
    {selection && <SourceDrawer selection={selection} onClose={closeSource} onOpenEpisode={onOpenEpisode} onListen={onListen} />}
    {preview && report && <PdfPreview report={report} pages={pages} onPagesChange={setPages} onClose={closePreview} onDownload={download} downloading={downloading} exportError={exportError} />}
    {toast && <div className="br-toast" role="status"><Check size={15} />{toast}</div>}
  </div>;
}
