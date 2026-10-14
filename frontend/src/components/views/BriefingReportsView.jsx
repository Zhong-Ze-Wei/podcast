import i18n from '../../i18n';
import { localizeUiMessage, formatUiDate, formatPeriodLabel } from '../../utils/localization';
import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle, ArrowLeft, Check, ChevronDown, Download, ExternalLink,
  Heart, Info, Loader2, Menu, MoreHorizontal, X,
} from 'lucide-react';
import { briefingReportsApi, tasksApi } from '../../services/api';
import FeedImage from '../common/FeedImage';
import { ListPagination } from '../common/ListControls';
import usePaginatedList from '../../hooks/usePaginatedList';
import { useTask, useTasks } from '../tasks/TasksContext';
import { importBrowserFavorites, loadReportFavoriteIds, restoreReportTask } from '../../utils/briefingPersistence';
import { getBriefingLayouts } from '../../utils/briefingLayouts';
import { readBriefingRoute, briefingPath, captureReadingPosition, restoreReadingPosition } from '../../utils/readingContext';
import BriefingPeriodBar from './BriefingPeriodBar';
import BriefingMaterialsDialog from './BriefingMaterialsDialog';
import BriefingQuotePopover from './BriefingQuotePopover';
import EpisodeAnalysisContent from '../briefing/EpisodeAnalysisContent';
import { evidenceGallery } from '../../utils/evidenceNavigation';
import './briefing-reports.css';
import './briefing-modes.css';
import './briefing-card-layout.css';


function payload(response) { return response?.data ?? response; }
function timeText(value) {
  if (value == null || !Number.isFinite(Number(value))) return '';
  const seconds = Math.floor(Number(value));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds % 3600 / 60);
  return `${hours ? `${hours}:` : ''}${hours ? String(minutes).padStart(2, '0') : minutes}:${String(seconds % 60).padStart(2, '0')}`;
}
function dateText(value) {
  return formatUiDate(value, i18n.resolvedLanguage, { month: 'long', day: 'numeric' });
}
function currentPeriodStart(type) {
  const day = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Hong_Kong' }).format(new Date());
  if (type === 'month') return day.slice(0, 7) + '-01';
  const date = new Date(day + 'T00:00:00Z');
  date.setUTCDate(date.getUTCDate() - (date.getUTCDay() + 6) % 7);
  return date.toISOString().slice(0, 10);
}
function readStored(storage, key, fallback) {
  const stored = storage.getItem(key);
  if (!stored) return fallback;
  try { return JSON.parse(stored); } catch { storage.removeItem(key); return fallback; }
}
function usableUrl(url) { return typeof url === 'string' && /^https?:\/\//i.test(url) ? url : null; }
function coverUrl(url) { return usableUrl(url) || (typeof url === 'string' && /^\/api\/media\/covers\/[^/]+\.(?:jpe?g|png|webp)(?:[?#].*)?$/i.test(url) ? url : null); }
function itemsIn(report) { return (report?.sections || []).flatMap(section => section.items || []); }
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
  const { t } = useTranslation();
  return <>
    <span className="br-translation-label">{card.translation ? t("ui.translation") : ''}</span>
    <blockquote>{card.translation || card.quote}</blockquote>
  </>;
}

function Excerpt({ card, provenance, sources, feeds, onRead, onListen, onSource, savedQuotes, onToggleQuote, onCopy, onEvidence, canFavorite = true, savingFavorite = false }) {
  const { t } = useTranslation();
  const RESOURCE_LABELS = { book: t("ui.book"), article: t("ui.article"), paper: t("ui.paper"), tool: t("ui.tool"), website: t("ui.website"), report: t("ui.report"), podcast: t("ui.podcast") };
  const CONNECTION_LABELS = { commonality: t("ui.commonGround"), difference: t("ui.difference"), complementary: t("ui.complementary") };
  const KIND_LABELS = { insight: t("ui.aITakeaway"), connection: t("ui.aISynthesis"), concept: t("ui.conceptsMethods"), resource: t("ui.episodeResources") };
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
    <p className="br-card-provenance br-field-label">{provenance}</p>
    <div className="br-excerpt-heading">{isQuote ? (card.brief || card.context) && <p className="br-brief">{card.brief || card.context}</p> : <span className="br-card-kicker">{card.kind === 'connection' ? t("ui.valueValueEpisodes", { value1: CONNECTION_LABELS[card.relation] || t("ui.connection"), value2: evidenceCount }) : card.kind === 'resource' ? `${RESOURCE_LABELS[card.resource_kind] || t("ui.resource")} · ${['recommended', 'explicit_recommendation'].includes(card.relation) ? t("ui.guestRecommendation") : t("ui.mentionedInTheEpisode")}` : KIND_LABELS[card.kind]}</span>}</div>
    <div className="br-excerpt-words">{isQuote ? <OriginalQuote card={card} /> : <><h2 className="br-mode-card-title">{card.title}</h2><p className="br-mode-card-text">{card.text}</p></>}</div>
    <div className="br-card-resource-slot">{card.kind === 'resource' && usableUrl(card.url) && <a className="br-text-button br-open-resource" href={card.url} target="_blank" rel="noopener noreferrer">{t("ui.openResource")} <ExternalLink size={14} /></a>}</div>
    <div className="br-card-evidence-slot">{evidence.length > 0 && <button className="br-card-evidence br-evidence-trigger" onClick={() => onEvidence({ title: card.title, quotes: evidence })}>{card.kind === 'resource' ? t("ui.supportingQuotation") : t("ui.quotationEvidence")} <span>{evidence.length} {t("ui.passages")}</span><ExternalLink size={13} /></button>}</div>
    <footer className="br-excerpt-footer">
      <div className="br-source-identity"><Cover source={{ ...source, feed: card.feed || source.feed }} feeds={feeds} /><div className="br-source-info"><div className="br-source-byline"><strong>{card.feed || source.feed || t("ui.sourcePodcast")}</strong>{card.speaker && <span>{card.speaker}</span>}</div>{episodeTitle && <span className="br-source-episode" title={episodeTitle}>{episodeTitle}</span>}</div></div>
      <div className="br-excerpt-actions">
        <button className="br-text-button" onClick={() => onRead(card.source_id)}>{t("ui.readEpisode")}</button>
        {episodeId && <button className="br-text-button br-listen" onClick={listen}>{t("ui.listenAt", { time: timeText(card.start) || t("ui.theBeginning") })}</button>}
        <button className={`br-favorite-button ${saved ? 'is-saved' : ''}`} aria-label={saved ? t("ui.unsaveThisItem") : t("ui.saveThisItem")} title={!canFavorite ? t("ui.yourAccountHasReadOnlyAccess2") : saved ? t("ui.savedClickToUnsave") : t("ui.saveToFavorites")} disabled={!canFavorite || savingFavorite} aria-pressed={saved} onClick={() => onToggleQuote(favoriteKey)}><Heart size={19} fill={saved ? 'currentColor' : 'none'} /></button>
        <details className="br-more"><summary aria-label={t("ui.moreItemActions")} title={t("ui.moreItemActions")}><MoreHorizontal size={19} /></summary><div className="br-more-menu">
          {isQuote && card.translation && <button onClick={event => { onEvidence({ title: card.brief || t("ui.originalEnglish"), quotes: [card] }); event.currentTarget.closest('.br-more').open = false; }}>{t("ui.originalEnglishTranslation")}</button>}
          <button onClick={event => { onSource(isQuote || !evidence.length ? card : evidence[0]); event.currentTarget.closest('.br-more').open = false; }}>{t("ui.viewInTranscript")}</button>
          {isQuote && <button onClick={() => onCopy(card)}>{t("ui.copyQuotationAndSource")}</button>}
        </div></details>
      </div>
    </footer>
  </article>;
}

function ExcerptItems({ layout, children }) {
  return ['paper', 'newspaper'].includes(layout)
    ? <div className={layout === 'paper' ? 'br-paper-items' : 'br-newspaper-items'}>{children}</div>
    : children;
}

function ReadingStyleSelect({ layout, disabled, onChange }) {
  const { t } = useTranslation();
  const LAYOUTS = getBriefingLayouts(t);
  return <label className="br-style-control">{t("ui.readingStyle")}<select aria-label={t("ui.readingStyle")} value={layout} disabled={disabled} onChange={event => onChange(event.target.value)}>{LAYOUTS.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>;
}

function EpisodeReading({ data, loading, error, working, feeds, onGenerate, onSource, onListen, onRetry, onEvidence }) {
  const { t } = useTranslation();
  const source = data?.source || {};
  const reading = data?.reading || data?.legacy_reading;
  return <article className="br-reading">
    <header className="br-reading-heading"><Cover source={source} feeds={feeds} large /><div><p>{source.feed}{source.duration > 0 ? ` · ${timeText(source.duration)}` : ''}</p><h1>{source.title || t("ui.loadingEpisode")}</h1></div></header>
    {loading ? <div className="br-loading"><Loader2 size={18} className="br-spinning" />{t("ui.loadingEpisodeAnalysis")}</div> : error ? <div className="br-notice br-notice-error" role="alert"><span>{localizeUiMessage(error, t)}</span><button className="br-text-button" onClick={onRetry}>{t("ui.reload2")}</button></div> : !reading ? <section className="br-reading-empty"><h2>{t("ui.noAnalysisForThisEpisodeYet")}</h2><p>{t("ui.readTheFullTranscriptAndSaveThe")}</p><button className="br-button br-button-primary" disabled={working} onClick={onGenerate}>{working && <Loader2 size={15} className="br-spinning" />}{t("ui.analyzeThisEpisode")}</button><button className="br-text-button" onClick={() => onSource({ source_id: source.id, source_title: source.title, feed: source.feed, episode_id: source.episode_id })}>{t("ui.readTranscriptFirst")}</button></section> : <>
      {data?.legacy_reading && !data?.reading && <div className="br-notice" role="status">{t("ui.thisSavedAnalysisWasBasedOnExcerpts")}</div>}
      <EpisodeAnalysisContent reading={reading} onEvidence={onEvidence} onSource={onSource} />
      <footer className="br-reading-footer"><button className="br-text-button" onClick={() => onSource({ source_id: source.id, source_title: source.title, feed: source.feed, episode_id: source.episode_id })}>{t("ui.readFullTranscript")}</button><span>{t("ui.analysisGeneratedOn")} {dateText(reading.generated_at)}</span>{!data?.reading && <button className="br-text-button" disabled={working} onClick={onGenerate}>{t("ui.analyzeFullTranscript")}</button>}</footer>
    </>}
  </article>;
}

export function SourceDrawer({ selection, onClose, onOpenEpisode, onListen }) {
  const { t } = useTranslation();
  const [source, setSource] = useState(null);
  const [error, setError] = useState('');
  const ref = useRef(null);
  const bodyRef = useRef(null);
  useModalFocus(ref, onClose);
  useEffect(() => {
    let active = true;
    setSource(null); setError('');
    briefingReportsApi.source(selection.source_id).then(response => { if (active) setSource(payload(response)); }).catch(err => { if (active) setError(err.message || t("ui.couldNotLoadTheOriginalTranscript")); });
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
    <div className="br-modal-heading"><div><span className="br-field-label">{source?.feed || selection.feed || t("ui.episodeTranscript")}</span><h2 id="br-source-title">{source?.title || selection.source_title || t("ui.loadingOriginalTranscript")}</h2></div><button className="br-icon-button" onClick={onClose} aria-label={t("ui.closeTranscript")}><X size={19} /></button></div>
    <div className="br-drawer-toolbar">{(selection.episode_id || source?.episode_id) && <><button className="br-button" onClick={() => { onClose(); onOpenEpisode(selection.episode_id || source.episode_id); }}>{t("ui.openEpisode")}</button><button className="br-button" onClick={() => onListen({ ...selection, episode_id: selection.episode_id || source.episode_id, original_url: source?.original_url })}>{t("ui.listenAt", { time: timeText(selection.start) || t("ui.theBeginning") })}</button></>}</div>
    <div className="br-source-body custom-scrollbar" ref={bodyRef}>{error ? <div className="br-notice br-notice-error" role="alert">{localizeUiMessage(error, t)}</div> : !source ? <div className="br-loading"><Loader2 size={18} className="br-spinning" />{t("ui.loadingSavedTranscript")}</div> : <>
      {quote && <div className="br-selected-quote"><strong>{t("ui.originalPassage")}{selection.start != null ? ` · ${timeText(selection.start)}` : ''}</strong><p>{quote}</p></div>}
      {segments.length ? segments.map((segment, index) => { const quoteIndex = quote && index === timedHighlight ? segment.text?.indexOf(quote) : -1; return <div className={`br-transcript-segment ${index === timedHighlight ? 'br-highlighted' : ''}`} key={index}><span>{timeText(segment.start ?? segment.time)}{segment.speaker ? ` · ${segment.speaker}` : ''}</span><p>{quoteIndex >= 0 ? <>{segment.text.slice(0, quoteIndex)}<mark>{quote}</mark>{segment.text.slice(quoteIndex + quote.length)}</> : segment.text}</p></div>; }) : <div className="br-full-text">{offset >= 0 ? <>{source.full_text.slice(0, offset)}<mark className="br-highlighted">{quote}</mark>{source.full_text.slice(offset + quote.length)}</> : source.full_text}</div>}
    </>}</div>
  </aside></div>, document.body);
}

function MaterialsDialog(props) {
  const ref = useRef(null);
  useModalFocus(ref, props.onClose);
  return <BriefingMaterialsDialog {...props} dialogRef={ref} CoverComponent={Cover} periodLabel={formatPeriodLabel(props.snapshot.period, i18n.resolvedLanguage)} />;
}

function PdfPreview({ report, pages, style, density, onDensityChange, onStyleChange, onPagesChange, onClose, onDownload, downloading, exportError }) {
  const { t } = useTranslation();
  const [html, setHtml] = useState('');
  const [error, setError] = useState('');
  const ref = useRef(null);
  useModalFocus(ref, onClose);
  useEffect(() => {
    let active = true;
    setHtml(''); setError('');
    briefingReportsApi.html(report.id, pages, style, density).then(response => { if (active) setHtml(typeof response === 'string' ? response : payload(response)); }).catch(async err => { if (active) setError(await errorText(err, t("ui.couldNotCreateTheReportPreview"))); });
    return () => { active = false; };
  }, [report.id, pages, style, density]);
  return createPortal(<div className="br-modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}><section className="br-pdf-modal" ref={ref} role="dialog" aria-modal="true" aria-labelledby="br-pdf-title">
    <div className="br-modal-heading"><div><h2 id="br-pdf-title">{t(`ui.modeName.${report.mode}`)} {t("ui.pDFPreview")}</h2><p>{pages === 'all' ? t("ui.exportAllItemsQuotationEvidenceAndSources") : t("ui.highlightsContainSelectedItemsOnlyChooseThe")}</p></div><button className="br-icon-button" onClick={onClose} aria-label={t("ui.closePDFPreview")}><X size={19} /></button></div>
    <div className="br-pdf-toolbar"><div className="br-segmented" aria-label={t("ui.exportRange")}><button className={pages === 'all' ? 'is-active' : ''} onClick={() => onPagesChange('all')}>{t("ui.fullReport")}</button><button className={pages === 1 ? 'is-active' : ''} onClick={() => onPagesChange(1)}>{t("ui.onePageHighlights")}</button><button className={pages === 2 ? 'is-active' : ''} onClick={() => onPagesChange(2)}>{t("ui.twoPageHighlights")}</button></div><label className="br-style-control">{t("ui.exportStyle")}<select aria-label={t("ui.pDFStyle")} value={style} onChange={event => onStyleChange(event.target.value)}><option value="paper">{t("ui.paper2")}</option><option value="newspaper">{t("ui.newspaper")}</option></select></label><label className="br-style-control">{t("ui.layoutDensity")}<select aria-label={t("ui.pDFLayoutDensity")} disabled={pages !== 'all'} title={pages === 'all' ? t("ui.textSizeAndSpacingForTheFull") : t("ui.highlightsUseAFixedLayout")} value={density} onChange={event => onDensityChange(event.target.value)}><option value="comfortable">{t("ui.comfortable")}</option><option value="compact">{t("ui.compact")}</option></select></label><button className="br-button br-button-primary" disabled={downloading || !html} onClick={onDownload}>{downloading ? <Loader2 size={14} className="br-spinning" /> : <Download size={14} />}{t("ui.downloadPDF")}</button></div>
    {exportError && <div className="br-notice br-notice-error br-pdf-error" role="alert">{localizeUiMessage(exportError, t)}</div>}
    <div className="br-pdf-preview">{error ? <div className="br-notice br-notice-error" role="alert">{localizeUiMessage(error, t)}</div> : !html ? <div className="br-loading"><Loader2 size={18} className="br-spinning" />{t("ui.preparingLayout")}</div> : <iframe title={t("ui.valuevaluePreview", { value1: pages === 'all' ? t("ui.full") : t("ui.valuePageHighlights", { value1: pages }), value2: t(`ui.modeName.${report.mode}`) })} srcDoc={html} sandbox="allow-popups allow-popups-to-escape-sandbox" />}</div>
  </section></div>, document.body);
}

export default function BriefingReportsView({ currentUser, feeds = [], onOpenEpisode, onListen, onOpenMenu, hasPlayer = false, section = 'reports', navigation, onNavigationStateChange, onSectionChange }) {
  const { t } = useTranslation();
  const MODES = [
  { id: 'core', name: t("ui.keyTakeaways") }, { id: 'quotes', name: t("ui.selectedQuotations") },
  { id: 'connections', name: t("ui.commonGroundDifferences") }, { id: 'concepts', name: t("ui.conceptsMethods") },
  { id: 'resources', name: t("ui.mentionedResources") },
];
  const LAYOUTS = getBriefingLayouts(t);
  const userId = currentUser?.id || currentUser?._id || 'guest';
  const storagePrefix = `podmaster_briefing_reading:${userId}`;
  const [layout, setLayout] = useState('paper');
  const [layoutLoading, setLayoutLoading] = useState(true);
  const [layoutSaving, setLayoutSaving] = useState(false);
  const [layoutError, setLayoutError] = useState('');
  const [mode, setMode] = useState('core');
  const savedOnly = section === 'saved';
  const [showAll, setShowAll] = useState(false);
  const [periodScope, setPeriodScope] = useState({ owner: userId, type: 'week', start: null });
  const [interests, setInterests] = useState([{ label: 'AI', enabled: true }, { label: 'LLM', enabled: true }]);
  const [materialsOpen, setMaterialsOpen] = useState(false);
  const [materialsLayout, setMaterialsLayout] = useState('gallery');
  const [pdfStyle, setPdfStyle] = useState('paper');
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [taskState, setTaskState] = useState({ owner: null, jobs: {} });
  const [progress, setProgress] = useState(null);
  const [submissions, setSubmissions] = useState({});
  const [pollError, setPollError] = useState('');
  const [selection, setSelection] = useState(null);
  const [preview, setPreview] = useState(false);
  const [pages, setPages] = useState('all');
  const [pdfDensity, setPdfDensity] = useState('comfortable');
  const [downloading, setDownloading] = useState(false);
  const [exportError, setExportError] = useState('');
  const [toast, setToast] = useState('');
  const [savedQuotes, setSavedQuotes] = useState([]);
  const [favoriteMode, setFavoriteMode] = useState('');
  const [favoriteRevision, setFavoriteRevision] = useState(0);
  const [savingFavorite, setSavingFavorite] = useState(null);
  const [favoriteReadingSources, setFavoriteReadingSources] = useState(null);
  const canFavorite = currentUser?.role !== 'viewer';
  const favorites = usePaginatedList(briefingReportsApi.favorites, { enabled: savedOnly, params: favoriteMode ? { mode: favoriteMode } : {}, scope: userId, revision: favoriteRevision, perPage: 20 });
  const tasks = useTasks();
  const [readingSource, setReadingSource] = useState(null);
  const [readings, setReadings] = useState({});
  const [readingLoading, setReadingLoading] = useState(false);
  const [readingError, setReadingError] = useState('');
  const [evidenceSelection, setEvidenceSelection] = useState(null);
  const viewRef = useRef(null);
  const userIdRef = useRef(userId);
  const readingScrollRef = useRef(0);
  const pendingRestoreRef = useRef(null);
  const scopeRef = useRef(periodScope);
  const snapshotRequestRef = useRef(0);
  const mountedRef = useRef(true);
  useEffect(() => { mountedRef.current = true; return () => { mountedRef.current = false; }; }, []);
  const isCurrentOwner = useCallback(owner => mountedRef.current && userIdRef.current === owner, []);
  scopeRef.current = periodScope;
  userIdRef.current = userId;
  const modes = (snapshot?.modes || MODES).map(item => ({ ...item, name: MODES.find(mode => mode.id === item.id)?.name || item.name, description: t(`ui.modeDescription.${item.id}`) }));
  const info = modes.find(item => item.id === mode) || MODES[0];
  const report = !loading ? snapshot?.reports?.[mode] : null;
  const sources = readingSource && favoriteReadingSources ? favoriteReadingSources : report?.sources || snapshot?.sources || [];
  const allItems = itemsIn(report);
  const failedEpisodeCount = report?.analysis?.failed_episodes?.length || 0;
  const hasUnfinishedAnalysis = report?.analysis?.partial && (failedEpisodeCount > 0 || report.analysis.skipped_chunks > 0);
  const isSaved = card => savedQuotes.includes(card.id);
  const filteredItems = allItems.filter(card => !savedOnly || isSaved(card));
  const visibleItems = showAll ? filteredItems : filteredItems.slice(0, 6);
  const matchingSourceCount = new Set(filteredItems.flatMap(card => [card.source_id, ...(card.source_ids || []), ...(card.evidence || []).map(quote => quote.source_id)]).filter(Boolean)).size;
  const period = snapshot?.period;
  const periodKey = !loading && period ? `${period.type}:${period.start}` : null;
  const task = taskState.owner === userId ? taskState.jobs[periodKey] : null;
  const { task: observedTask, error: taskError } = useTask(task?.id);
  const working = Boolean(task || submissions[periodKey]);
  const updateTask = useCallback((key, next) => {
    setTaskState(current => {
      const jobs = { ...(current.owner === userId ? current.jobs : {}) };
      if (next) jobs[key] = next;
      else delete jobs[key];
      return { owner: userId, jobs };
    });
  }, [userId]);
  const hasMaterials = (period?.transcript_count ?? sources.length) > 0;
  const readingContext = () => ({ owner: userId, periodType: period?.type || periodScope.type, periodStart: period?.start || periodScope.start, mode, selectedTag: '', showAll, readingSource, reportScrollTop: readingScrollRef.current, scroll: captureReadingPosition(viewRef.current) });
  const publishContext = () => onNavigationStateChange(readingContext());
  useEffect(() => {
    publishContext();
    if (!loading && window.location.pathname.startsWith('/briefing')) {
      const context = readingContext();
      window.history.replaceState({ ...window.history.state, briefingContext: context }, '', briefingPath(savedOnly ? 'saved' : 'reports', context));
    }
  }, [periodScope.type, period?.start, mode, showAll, readingSource, loading, savedOnly, onNavigationStateChange]);
  const closeSource = useCallback(() => setSelection(null), []);
  const closePreview = useCallback(() => setPreview(false), []);
  const closeEvidence = useCallback(() => setEvidenceSelection(null), []);
  const closeMaterials = useCallback(() => setMaterialsOpen(false), []);
  const reload = useCallback(async () => {
    const requested = { ...scopeRef.current };
    const requestId = ++snapshotRequestRef.current;
    const current = () => isCurrentOwner(userId) && requestId === snapshotRequestRef.current && scopeRef.current.type === requested.type && scopeRef.current.start === requested.start;
    try {
      const data = payload(await briefingReportsApi.modes({ period_type: requested.type, ...(requested.start ? { period_start: requested.start } : {}) }));
      if (current()) setSnapshot(data);
      return data;
    } catch (error) {
      if (current()) throw error;
      return null;
    }
  }, [userId, isCurrentOwner]);
  const readEpisode = sourceId => { if (!readingSource) readingScrollRef.current = viewRef.current?.scrollTop || 0; setReadingSource(sourceId); setReadingError(''); };
  useLayoutEffect(() => { viewRef.current?.scrollTo({ top: readingSource ? 0 : readingScrollRef.current }); }, [readingSource]);
  useLayoutEffect(() => {
    if (loading || !pendingRestoreRef.current || (readingSource && (readingLoading || !readings[readingSource]))) return;
    restoreReadingPosition(viewRef.current, pendingRestoreRef.current);
    pendingRestoreRef.current = null;
    publishContext();
  }, [loading, readingSource, readingLoading, readings, report?.id, showAll]);

  useEffect(() => {
    readingScrollRef.current = 0;
    setLoading(true); setSnapshot(null); setReadingSource(null); setReadings({}); setError(''); setPreview(false); setSelection(null); setProgress(null); setPollError(''); setSubmissions({}); setReadingLoading(false); setDownloading(false); setExportError(''); setEvidenceSelection(null); setMaterialsOpen(false); setShowAll(false);
    setLayout('paper'); setMaterialsLayout('gallery');
    const storedMode = localStorage.getItem(`${storagePrefix}:mode`);
    const initialMode = MODES.some(item => item.id === storedMode) ? storedMode : 'core';
    setMode(initialMode);
    const savedPeriod = readStored(localStorage, `${storagePrefix}:period`, null);
    const routeContext = readBriefingRoute(window.location.search);
    const restore = navigation?.restore ? navigation : null;
    const query = new URLSearchParams(window.location.search);
    const queryType = query.get('period_type');
    const queryStart = query.get('period_start');
    const validQuery = ['week', 'month'].includes(queryType) && /^\d{4}-\d{2}-\d{2}$/.test(queryStart || '') && Number.isFinite(Date.parse(queryStart)) && new Date(queryStart).toISOString().slice(0, 10) === queryStart;
    if (restore || query.has('mode')) setMode((restore || routeContext).mode);
    setShowAll(Boolean((restore || routeContext).showAll));
    setReadingSource((restore || routeContext).readingSource || null);
    readingScrollRef.current = restore?.reportScrollTop || 0;
    pendingRestoreRef.current = restore?.scroll || (window.history.state?.briefingContext?.owner === userId ? window.history.state.briefingContext.scroll : null);
    setPeriodScope(restore ? { owner: userId, type: restore.periodType, start: restore.periodStart } : validQuery ? { owner: userId, type: queryType, start: queryStart } : { owner: userId, type: savedPeriod?.type === 'month' ? 'month' : 'week', start: savedPeriod?.start || null });
    setInterests([{ label: 'AI', enabled: true }, { label: 'LLM', enabled: true }]);
    setTaskState({ owner: userId, jobs: {} });
    setSavedQuotes([]); setFavoriteReadingSources(null); setFavoriteMode('');
  }, [storagePrefix]);
  useEffect(() => {
    if (!navigation) return;
    setSelection(null); setEvidenceSelection(null); setPreview(false);
    if (navigation.restore) {
      setReadingSource(navigation.readingSource || null); setShowAll(Boolean(navigation.showAll));
      readingScrollRef.current = navigation.reportScrollTop || 0;
      pendingRestoreRef.current = navigation.scroll;
    } else { setReadingSource(navigation.readingSource || null); setShowAll(Boolean(navigation.showAll)); viewRef.current?.scrollTo({ top: 0 }); }
    if (MODES.some(item => item.id === navigation.mode)) setMode(navigation.mode);
    if (['week', 'month'].includes(navigation.periodType)) {
      const start = navigation.periodStart || null;
      if (periodScope.owner === userId && periodScope.type === navigation.periodType && (!start || periodScope.start === start)) {
        reload().catch(err => setError(err.message || t("ui.couldNotLoadTheBriefing")));
      }
      setPeriodScope(current => current.type === navigation.periodType && (!start || current.start === start)
        ? current : { owner: userId, type: navigation.periodType, start });
    }
  }, [navigation]);
  useEffect(() => {
    if (periodScope.owner !== userId) return;
    let active = true;
    const requestId = ++snapshotRequestRef.current;
    setLoading(true); setError(''); setProgress(null); setPollError(''); setMaterialsOpen(false); setSelection(null); setEvidenceSelection(null); setPreview(false);
    briefingReportsApi.modes({ period_type: periodScope.type, ...(periodScope.start ? { period_start: periodScope.start } : {}) }).then(async response => {
      if (!active || requestId !== snapshotRequestRef.current) return;
      const data = payload(response);
      setSnapshot(data);
      if (data.preferences?.interests) setInterests(data.preferences.interests);
      if (data.period) {
        localStorage.setItem(`${storagePrefix}:period`, JSON.stringify({ type: data.period.type, start: data.period.start }));
        const url = new URL(window.location.href);
        url.searchParams.set('period_type', data.period.type);
        url.searchParams.set('period_start', data.period.start);
        window.history.replaceState(window.history.state, '', url);
      }
    }).catch(err => { if (active && requestId === snapshotRequestRef.current) { setSnapshot(null); setError(err.message || t("ui.couldNotLoadTheBriefing")); } }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [periodScope.owner, periodScope.type, periodScope.start, storagePrefix]);
  useEffect(() => {
    let active = true;
    setLayoutLoading(true); setLayoutSaving(false); setLayoutError('');
    briefingReportsApi.preferences().then(response => {
      if (active) { setLayout(payload(response).layout || 'paper'); setMaterialsLayout(payload(response).materials_layout || 'gallery'); }
    }).catch(err => { if (active) setLayoutError(err.message || t("ui.couldNotLoadYourReadingStyleSelect")); }).finally(() => { if (active) setLayoutLoading(false); });
    return () => { active = false; };
  }, [userId]);
  useEffect(() => {
    if (!canFavorite) return;
    let active = true;
    importBrowserFavorites(localStorage, `${storagePrefix}:quotes`, briefingReportsApi.importFavorites).then(result => {
      if (!active) return;
      setFavoriteRevision(value => value + 1);
      if (result.unresolved.length) setToast(t("ui.valueOlderFavoritesCouldNotBeMatched", { value1: result.unresolved.length }));
    }).catch(err => { if (active) setError(err.message || t("ui.olderFavoritesCouldNotBeImportedBrowser")); });
    return () => { active = false; };
  }, [storagePrefix, canFavorite]);
  useEffect(() => {
    if (!report) return;
    let active = true;
    setSavedQuotes([]);
    loadReportFavoriteIds(report, briefingReportsApi.favorites).then(ids => { if (active) setSavedQuotes(ids); }).catch(err => { if (active) setError(err.message || t("ui.couldNotLoadSavedItemStatus")); });
    return () => { active = false; };
  }, [report?.id, favoriteRevision]);
  useEffect(() => { if (!loading) localStorage.setItem(`${storagePrefix}:mode`, mode); }, [mode, loading, storagePrefix]);
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(''), 3000); return () => clearTimeout(timer); }, [toast]);
  useEffect(() => { setEvidenceSelection(null); setPreview(false); }, [report?.id]);

  useEffect(() => {
    if (!readingSource) return;
    let active = true;
    setReadingLoading(true); setReadingError('');
    briefingReportsApi.reading(readingSource).then(response => { if (active) setReadings(previous => ({ ...previous, [readingSource]: payload(response) })); }).catch(err => { if (active) setReadingError(err.message || t("ui.couldNotLoadThisEpisodeSAnalysis")); }).finally(() => { if (active) setReadingLoading(false); });
    return () => { active = false; };
  }, [readingSource]);
  useEffect(() => {
    if (!periodKey) return;
    let active = true;
    restoreReportTask(period, readingSource, tasksApi.list).then(job => {
      if (!active) return;
      if (!job) return;
      updateTask(periodKey, { id: job.id, kind: job.report_context?.kind, mode: job.report_context?.mode, sourceId: job.report_context?.source_id });
      tasks.register(job);
    }).catch(err => { if (active) setPollError(err.message || t("ui.couldNotLoadGenerationProgress")); });
    return () => { active = false; };
  }, [periodKey, readingSource, updateTask, tasks.register]);
  useEffect(() => {
    if (!task || !observedTask) return;
    const state = observedTask;
    setProgress(state); setPollError(taskError || '');
    if (state.status === 'completed') {
      if (state.result?.reading) { const reading = state.result.reading; setReadings(previous => ({ ...previous, [reading.source_id]: { ...previous[reading.source_id], reading, source: reading.source } })); }
      updateTask(periodKey, null); setProgress(null);
      if (task.kind !== 'reading') reload().catch(err => setError(err.message || t("ui.theBriefingIsSavedButTheList")));
    } else if (['failed', 'cancelled'].includes(state.status)) {
      setError(state.status === 'cancelled' ? t("ui.generationWasCanceledPreviousContentRemainsAvailable") : state.error || t("ui.generationDidNotFinishPreviousContentRemains"));
      updateTask(periodKey, null); setProgress(null);
    }
  }, [task, observedTask, taskError, reload, periodKey, updateTask]);

  const generate = async (kind, target) => {
    const owner = userId;
    const key = periodKey;
    const requested = { ...scopeRef.current };
    const current = () => isCurrentOwner(owner) && scopeRef.current.type === requested.type && scopeRef.current.start === requested.start;
    const scope = { period_type: period.type, period_start: period.start, interests: interests.filter(item => item.enabled).map(item => item.label) };
    setSubmissions(previous => ({ ...previous, [key]: true })); setError(''); setPollError('');
    try {
      const data = payload(await (kind === 'reading' ? briefingReportsApi.generateReading(target, scope) : briefingReportsApi.generateModes({ mode: target, ...scope })));
      if (!isCurrentOwner(owner)) return;
      const source = kind === 'reading' ? sources.find(item => item.id === target) || readings[target]?.source : null;
      tasks.register({ id: data.task_id, type: 'briefing-report', status: 'pending', progress: 0, episode_id: source?.episode_id, episode_title: source?.title, feed_title: source?.feed, report_period: { type: period.type, start: period.start }, report_context: { kind, mode: kind === 'reading' ? undefined : target, source_id: kind === 'reading' ? target : undefined } });
      tasks.refresh();
      updateTask(key, { id: data.task_id, kind, sourceId: kind === 'reading' ? target : undefined, mode: kind === 'reading' ? undefined : target, scope });
      if (current()) setProgress({ progress: 0, progress_message: t("ui.taskSubmitted") });
    } catch (err) { if (current()) setError(err.message || t("ui.couldNotStartGenerationPreviousContentIs")); }
    finally { if (isCurrentOwner(owner)) setSubmissions(previous => { const next = { ...previous }; delete next[key]; return next; }); }
  };
  const toggleQuote = async (id, reportId = report?.id, alreadySaved = savedQuotes.includes(id)) => {
    if (!canFavorite || savingFavorite) return;
    const owner = userId;
    setSavingFavorite(id); setError('');
    try {
      await (alreadySaved ? briefingReportsApi.unfavorite(id) : briefingReportsApi.favorite(id, reportId));
      if (!isCurrentOwner(owner)) return;
      setSavedQuotes(current => alreadySaved ? current.filter(item => item !== id) : [...current, id]);
      setFavoriteRevision(value => value + 1);
    } catch (err) { if (isCurrentOwner(owner)) setError(err.message || t("ui.couldNotSaveThisItemPleaseRetry")); }
    finally { if (isCurrentOwner(owner)) setSavingFavorite(null); }
  };
  const copyQuote = async card => {
    const source = sources.find(item => item.id === card.source_id);
    const text = [card.quote, card.translation ? t("ui.translationValue", { value1: card.translation }) : '', `${card.feed || source?.feed || ''} · ${card.source_title || source?.title || ''}${card.speaker ? ` · ${card.speaker}` : ''}${card.start != null ? ` · ${timeText(card.start)}` : ''}`].filter(Boolean).join('\n\n');
    try { await navigator.clipboard.writeText(text); setToast(t("ui.quotationAndSourceCopied")); } catch { setError(t("ui.theBrowserBlockedClipboardAccessSelectAnd")); }
  };
  const download = async () => {
    if (!report) return;
    const owner = userId;
    setDownloading(true); setError(''); setExportError('');
    try {
      const response = await briefingReportsApi.pdf(report.id, pages, pdfStyle, pdfDensity);
      if (!isCurrentOwner(owner)) return;
      const blob = response instanceof Blob ? response : new Blob([response], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob); const link = document.createElement('a');
      link.href = url; link.download = `PodMaster-${info.name}-${pages === 'all' ? t("ui.fullReport") : t("ui.valuePageHighlights", { value1: pages })}.pdf`;
      document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { const message = await errorText(err, t("ui.pDFExportFailedYourBriefingIsPreserved")); if (isCurrentOwner(owner)) { setError(message); setExportError(message); } }
    finally { if (isCurrentOwner(owner)) setDownloading(false); }
  };
  const retryReading = async () => { const owner = userId; setReadingLoading(true); setReadingError(''); try { const data = payload(await briefingReportsApi.reading(readingSource)); if (isCurrentOwner(owner)) setReadings(previous => ({ ...previous, [readingSource]: data })); } catch (err) { if (isCurrentOwner(owner)) setReadingError(err.message || t("ui.couldNotLoadThisEpisodeSAnalysis")); } finally { if (isCurrentOwner(owner)) setReadingLoading(false); } };
  const changeLayout = async next => {
    const owner = userId;
    const previous = layout;
    setLayout(next); setLayoutSaving(true); setLayoutError('');
    try {
      await briefingReportsApi.savePreferences({ layout: next });
    } catch (err) {
      if (isCurrentOwner(owner)) { setLayout(previous); setLayoutError(err.message || t("ui.couldNotSaveTheReadingStyleSelect")); }
    } finally { if (isCurrentOwner(owner)) setLayoutSaving(false); }
  };
  const openPreview = () => { setPdfStyle(layout === 'newspaper' ? 'newspaper' : 'paper'); setPreview(true); };
  const excerptProps = { canFavorite, savingFavorite: Boolean(savingFavorite), sources, feeds, onRead: readEpisode, onListen, onSource: setSelection, savedQuotes, onToggleQuote: toggleQuote, onCopy: copyQuote, onEvidence: item => setEvidenceSelection({ ...evidenceGallery(item, allItems), sources }) };
  const readingData = readingSource ? readings[readingSource] || { source: sources.find(source => source.id === readingSource) } : null;

  return <div ref={viewRef} onScroll={publishContext} className={`briefing-reports-view custom-scrollbar ${hasPlayer ? 'br-has-player' : ''}`}>
    <link rel="stylesheet" href="/api/briefing-reports/reading-theme.css" />
    <header className="br-page-header"><div className="br-page-heading"><button className="br-menu-button" onClick={onOpenMenu} aria-label={t("ui.openMenu")}><Menu size={20} /></button>{readingSource && section !== 'settings' ? <button className="br-back-button" onClick={() => setReadingSource(null)}><ArrowLeft size={17} />{t("ui.backToBriefing")}</button> : <div><h1>{section === 'settings' ? t("ui.briefingSettings") : savedOnly ? t("ui.savedBriefingItems") : t("ui.aIBriefing")}</h1><p>{section === 'settings' ? t("ui.interestsAutomaticGenerationAndReadingStyle") : loading ? t("ui.loadingBriefing") : period ? savedOnly ? t("ui.savedContentAndOriginalSourcesAcrossPeriods") : `${formatPeriodLabel(period, i18n.resolvedLanguage)}${period.is_current ? t("ui.periodInProgress") : ''}` : t("ui.readEpisodesBasedOnYourInterests")}</p></div>}</div></header>
    <main className="br-main">

      {section !== 'settings' && !savedOnly && !readingSource && <>
        <BriefingPeriodBar period={period} periods={snapshot?.periods || []} periodType={periodScope.type} loading={loading} onPeriodType={type => setPeriodScope({ owner: userId, type, start: null })} onPeriod={item => setPeriodScope({ owner: userId, type: periodScope.type, start: item.start })} onMaterials={() => setMaterialsOpen(true)} onCurrent={() => setPeriodScope({ owner: userId, type: periodScope.type, start: currentPeriodStart(periodScope.type) })} />
        <div className="br-mobile-controls"><label>{t("ui.contentSection")}<select aria-label={t("ui.chooseBriefingSection")} value={mode} onChange={event => { setMode(event.target.value); viewRef.current?.scrollTo({ top: 0 }); }}>{modes.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div>
        <div className="br-toolbar br-modes-toolbar"><nav className="br-content-tabs" aria-label={t("ui.fiveContentSections")}>{modes.map(item => <button key={item.id} className={mode === item.id ? 'is-active' : ''} aria-pressed={mode === item.id} onClick={() => { setMode(item.id); viewRef.current?.scrollTo({ top: 0 }); }}>{item.name}</button>)}</nav><div className="br-toolbar-actions">
          <ReadingStyleSelect layout={layout} disabled={layoutLoading || layoutSaving} onChange={changeLayout} />
          {report && <button className="br-button br-export" onClick={openPreview}>{t("ui.exportPDF")}</button>}
        </div></div>
        {report && <div className="br-filter-result" aria-live="polite"><span>{filteredItems.length} {t("ui.items")} {matchingSourceCount} {t("ui.episodes3")}</span></div>}
      </>}
      {layoutError && <div className="br-notice br-notice-error" role="alert"><AlertCircle size={17} /><span>{localizeUiMessage(layoutError, t)}</span><button className="br-icon-button" onClick={() => setLayoutError('')} aria-label={t("ui.dismissReadingStyleNotice")}><X size={16} /></button></div>}
      {error && <div className="br-notice br-notice-error" role="alert"><AlertCircle size={17} /><span>{localizeUiMessage(error, t)}</span><button className="br-text-button" onClick={() => { setError(''); reload().catch(err => setError(err.message || t("ui.reloadFailed"))); }}>{t("ui.reload2")}</button><button className="br-icon-button" onClick={() => setError('')} aria-label={t("ui.dismissNotice")}><X size={16} /></button></div>}
      {!savedOnly && !readingSource && !report && snapshot?.episode_analysis?.completed_episodes > 0 && <div className="br-notice" role="status"><span>{t("ui.available")} {snapshot.episode_analysis.completed_episodes} {t("ui.fullTranscriptAnalysesReusableInWeeklyAnd")}</span></div>}
      {working && <div className="br-task-status" role="status"><div><Loader2 size={16} className="br-spinning" /><strong>{task?.kind === 'reading' ? t("ui.analyzingThisEpisode") : task?.mode === 'all' ? t("ui.generatingAllFiveSections") : t("ui.generatingValue", { value1: modes.find(item => item.id === task?.mode)?.name || t("ui.briefing") })}</strong><span>{localizeUiMessage(progress?.progress_message || progress?.message || t("ui.taskSubmitted2"), t)}</span></div><progress max="100" value={progress?.progress || 0} />{pollError && <p>{localizeUiMessage(pollError, t)}</p>}</div>}
      {section !== 'settings' && (readingSource ? <EpisodeReading data={readingData} loading={readingLoading} error={readingError} working={working} feeds={feeds} onGenerate={() => generate('reading', readingSource)} onSource={setSelection} onListen={onListen} onRetry={retryReading} onEvidence={setEvidenceSelection} /> : savedOnly ? <>
        <div className="br-toolbar"><span>{favorites.pagination.total} {t("ui.savedItemsAcrossAllPeriods")}</span><div className="br-toolbar-actions"><ReadingStyleSelect layout={layout} disabled={layoutLoading || layoutSaving} onChange={changeLayout} /><label className="br-style-control">{t("ui.contentType")}<select aria-label={t("ui.filterSavedItemsByType")} value={favoriteMode} onChange={event => setFavoriteMode(event.target.value)}><option value="">{t("ui.allContent")}</option>{MODES.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div></div>
        <section className={`br-quote-layout br-layout-${layout}`} aria-label={t("ui.savedBriefingItemsAcrossPeriods")}><ExcerptItems layout={layout}>{favorites.data.map(favorite => <Excerpt key={favorite.item_id} {...excerptProps} provenance={`${formatPeriodLabel(favorite.report.period, i18n.resolvedLanguage)} · ${MODES.find(mode => mode.id === favorite.report.mode)?.name || favorite.report.title}`} card={favorite.item} sources={favorite.report.sources || []} savedQuotes={[favorite.item_id]} onToggleQuote={() => toggleQuote(favorite.item_id, favorite.report_id, true)} onRead={sourceId => { setFavoriteReadingSources(favorite.report.sources || []); readEpisode(sourceId); }} onEvidence={item => setEvidenceSelection({ ...evidenceGallery(item, itemsIn(favorite.report)), sources: favorite.report.sources || [] })} />)}</ExcerptItems></section>
        {!favorites.loading && !favorites.error && !favorites.data.length && <div className="br-empty"><h2>{t("ui.noSavedItemsYet")}</h2><p>{t("ui.clickTheHeartWhileReadingToSave")}</p><button className="br-button" onClick={() => onSectionChange('reports')}>{t("ui.readBriefing")}</button></div>}
        <ListPagination list={favorites} />
      </> : loading ? <div className="br-loading"><Loader2 size={20} className="br-spinning" />{t("ui.loadingSavedBriefing")}</div> : !report ? <div className="br-empty"><h2>{!period?.total_count ? t("ui.noEpisodesInThisPeriod") : !hasMaterials ? t("ui.noTranscriptsToAnalyzeInThisPeriod") : t("ui.noValueGeneratedForThisPeriodYet", { value1: info.name })}</h2><p>{!period?.total_count ? t("ui.browseAnotherWeekOrMonth") : !hasMaterials ? t("ui.onceTranscriptsAreAvailableAnalyzeEachEpisode") : t("ui.valueScreenTitlesByInterestsAnalyzeEach", { value1: formatPeriodLabel(period, i18n.resolvedLanguage), value2: info.name })}</p>{hasMaterials && <><button className="br-button br-button-primary" disabled={working || !canFavorite} onClick={() => generate('modes', mode)}>{t("ui.generateThisSection")}</button><button className="br-button br-generate-all" disabled={working || !canFavorite} onClick={() => generate('modes', 'all')}>{t("ui.generateAllFiveSections")}</button></>}</div> : <>
        {!['paper', 'newspaper'].includes(layout) && <header className="br-mode-intro"><h2>{info.name}</h2>{info.description && <p>{info.description}</p>}</header>}
        <section className={`br-quote-layout br-layout-${layout}`} aria-label={t("ui.valueValueLayout", { value1: info.name, value2: LAYOUTS.find(item => item.id === layout).name })}>
          {['paper', 'newspaper'].includes(layout) && <header className="br-paper-heading"><div><span>{t("ui.podMasterAIBriefing")}</span><h2>{info.name}</h2></div><span>{formatPeriodLabel(period, i18n.resolvedLanguage) || dateText(report.generated_at)}</span></header>}
          <ExcerptItems layout={layout}>{visibleItems.map(card => <Excerpt key={`${report.id}:${card.id}`} card={card} {...excerptProps} />)}</ExcerptItems>
          {['paper', 'newspaper'].includes(layout) && <footer className="br-paper-footer">{t("ui.includes")} {sources.length} {t("ui.transcriptsShowing")} {visibleItems.length} {t("ui.itemsOf")} {filteredItems.length} {t("ui.itemsSourcesAvailableForAll")}</footer>}
        </section>
        {filteredItems.length > 6 && <div className="br-expand-more"><button className="br-button" aria-expanded={showAll} onClick={() => setShowAll(current => !current)}>{showAll ? t("ui.collapseToTheFirst6Items") : t("ui.showValueMoreItems", { value1: filteredItems.length - 6 })}<ChevronDown size={14} /></button></div>}
        {!filteredItems.length && <div className="br-empty"><h2>{savedOnly ? t("ui.noSavedItemsMatchThisFilter") : t("ui.noContentMatchesTheCurrentInterests")}</h2><p>{savedOnly ? t("ui.clickTheHeartBelowAnItemTo") : t("ui.adjustYourInterestsInSettingsAtThe")}</p></div>}
        <footer className="br-edition-footer">
          <span className="br-edition-meta">{t("ui.generatedOn")} {dateText(report.generated_at)}
            {(report.matches_current_selection === false || report.analysis?.partial) && <button type="button" className="br-report-note" aria-label={t('briefing.reportInfo')} aria-describedby="br-report-info-details">
              <Info size={14} aria-hidden="true" />
              <span className="br-report-tooltip" id="br-report-info-details" role="tooltip">
                {report.matches_current_selection === false && <span>{t('briefing.savedVersion', { date: dateText(report.generated_at) })}</span>}
                {report.analysis?.partial && <span>{failedEpisodeCount > 0 ? t("ui.analyzedValueValueEpisodesValueRemainUnfinished", { value1: report.analysis.completed_episodes, value2: report.analysis.total_episodes, value3: failedEpisodeCount }) : <>{t("ui.skipped")} {report.analysis.rejected_items} {t("ui.itemsThatCouldNotBeVerified")}{report.analysis.skipped_chunks > 0 ? t("ui.valueAnalysisChunksRemainUnfinishedContinueUsing", { value1: report.analysis.skipped_chunks }) : t("ui.theRemainingContentIsSavedSourcesAre")}</>}</span>}
              </span>
            </button>}
          </span>
          {hasUnfinishedAnalysis && <button className="br-text-button" disabled={working || !canFavorite} onClick={() => generate('modes', mode)}>{t("ui.resumeUnfinishedAnalysis")}</button>}
          <button className="br-text-button" disabled={working || !canFavorite} onClick={() => generate('modes', 'all')}>{t("ui.generateAllFiveSections")}</button>
          <button className="br-text-button" disabled={working || !canFavorite} onClick={() => generate('modes', mode)}>{t("ui.regenerateThisSection")}</button>
        </footer>
      </>)}
    </main>
    {evidenceSelection && <BriefingQuotePopover selection={evidenceSelection} sources={evidenceSelection.sources || sources} onClose={closeEvidence} onRead={readEpisode} onListen={onListen} onSource={setSelection} />}
    {materialsOpen && snapshot && <MaterialsDialog snapshot={snapshot} feeds={feeds} layout={materialsLayout} onClose={closeMaterials} onRead={readEpisode} onOpenEpisode={onOpenEpisode} />}
    {selection && <SourceDrawer selection={selection} onClose={closeSource} onOpenEpisode={onOpenEpisode} onListen={onListen} />}
    {preview && report && <PdfPreview report={report} density={pdfDensity} onDensityChange={setPdfDensity} style={pdfStyle} onStyleChange={setPdfStyle} pages={pages} onPagesChange={setPages} onClose={closePreview} onDownload={download} downloading={downloading} exportError={localizeUiMessage(exportError, t)} />}
    {toast && <div className="br-toast" role="status"><Check size={16} />{localizeUiMessage(toast, t)}</div>}
  </div>;
}
