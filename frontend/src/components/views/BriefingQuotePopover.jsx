import { useTranslation } from 'react-i18next';
import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowLeft, ArrowRight, Headphones, X } from 'lucide-react';
import { evidenceIndex, evidenceSwipeStep } from '../../utils/evidenceNavigation';
import { briefingReportsApi } from '../../services/api';
import './briefing-reports.css';
import './briefing-modes.css';

function timeText(value) {
  if (value == null || !Number.isFinite(Number(value))) return '';
  const seconds = Math.floor(Number(value));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds % 3600 / 60);
  return (hours ? hours + ':' + String(minutes).padStart(2, '0') : minutes) + ':' + String(seconds % 60).padStart(2, '0');
}

export default function BriefingQuotePopover({ selection, sources, onClose, onRead, onListen, onSource }) {
  const { t } = useTranslation();
  const [index, setIndex] = useState(() => evidenceIndex(selection.initialIndex || 0, 0, selection.quotes.length));
  const [original, setOriginal] = useState(false);
  const [underlines, setUnderlines] = useState({});
  const [selectedRange, setSelectedRange] = useState(null);
  const [scrollable, setScrollable] = useState(false);
  const [atEnd, setAtEnd] = useState(true);
  const [dragOffset, setDragOffset] = useState(0);
  // 原文依据多为英文逐字引文：打开时对缺 translation 的条目按需补译（后端按引文哈希缓存）
  const [zhMap, setZhMap] = useState({});
  const gesture = useRef(null);
  const ref = useRef(null);
  const bodyRef = useRef(null);
  const readingRef = useRef(null);
  const quoteRef = useRef(null);
  const quotes = selection.quotes;
  const card = quotes[index];
  const zhText = item => item.translation || zhMap[item.id] || '';
  const source = sources.find(item => item.id === card.source_id) || {};
  const episodeId = card.episode_id || source.episode_id;
  const text = original ? card.quote : (zhText(card) || card.quote);
  const underlineKey = `${index}:${original ? 'original' : 'reading'}`;
  const underline = underlines[underlineKey];
  const navigate = step => setIndex(current => evidenceIndex(current, step, quotes.length));
  const measureScroll = () => {
    const body = bodyRef.current;
    setScrollable(body.scrollHeight > body.clientHeight + 1);
    setAtEnd(body.scrollHeight - body.scrollTop <= body.clientHeight + 1);
  };

  useEffect(() => {
    setZhMap({});
    const list = selection.quotes || [];
    const sourceId = list[0] && list[0].source_id;
    // 已有 translation 或本身是中文的都不需要补译
    const need = list.filter(item => item.quote && !item.translation && !/[\u4e00-\u9fff]/.test(item.quote));
    if (!sourceId || need.length === 0) return undefined;
    let alive = true;
    briefingReportsApi.translateEvidence(sourceId, need.map(item => ({ id: item.id, quote: item.quote })))
      .then(res => { if (alive) setZhMap(res.data?.translations || res.translations || {}); })
      .catch(() => {});
    return () => { alive = false; };
  }, [selection]);

  useEffect(() => {
    const before = document.activeElement;    const dialog = ref.current;
    dialog.querySelector('[data-close-quote]')?.focus();
    const onKey = event => {
      if (event.key === 'Escape') onClose();
      const navigate = !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey;
      if (navigate && event.key === 'ArrowLeft' && quotes.length > 1) { event.preventDefault(); setIndex(current => evidenceIndex(current, -1, quotes.length)); }
      if (navigate && event.key === 'ArrowRight' && quotes.length > 1) { event.preventDefault(); setIndex(current => evidenceIndex(current, 1, quotes.length)); }
      if (event.key !== 'Tab') return;
      const elements = [...dialog.querySelectorAll('button:not([disabled]), a[href], [tabindex="0"]')];
      const first = elements[0];
      const last = elements.at(-1);
      if (!dialog.contains(document.activeElement)) { event.preventDefault(); (event.shiftKey ? last : first)?.focus(); }
      else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); before?.focus(); };
  }, [onClose, quotes.length]);
  useEffect(() => {
    setOriginal(false);
    setDragOffset(0);
  }, [index]);
  useEffect(() => {
    bodyRef.current.scrollTop = 0;
    setSelectedRange(null);
    window.getSelection().removeAllRanges();
    if (!ref.current.contains(document.activeElement)) ref.current.querySelector('button')?.focus();
  }, [index, original]);
  useEffect(() => {
    const body = bodyRef.current;
    const observer = new ResizeObserver(measureScroll);
    observer.observe(body);
    observer.observe(readingRef.current);
    measureScroll();
    return () => observer.disconnect();
  }, [index, original]);
  useEffect(() => {
    const select = () => {
      const selection = window.getSelection();
      if (selection.isCollapsed || !selection.rangeCount || !quoteRef.current.contains(selection.anchorNode) || !quoteRef.current.contains(selection.focusNode)) {
        setSelectedRange(null);
        return;
      }
      const range = selection.getRangeAt(0);
      const before = range.cloneRange();
      before.selectNodeContents(quoteRef.current);
      before.setEnd(range.startContainer, range.startOffset);
      const start = before.toString().length;
      setSelectedRange({ start, end: start + range.toString().length });
    };
    document.addEventListener('selectionchange', select);
    return () => document.removeEventListener('selectionchange', select);
  }, []);

  const underlineSelection = () => {
    setUnderlines(current => ({ ...current, [underlineKey]: selectedRange }));
    window.getSelection().removeAllRanges();
    setSelectedRange(null);
  };

  const startDrag = event => {
    if (quotes.length < 2 || event.button !== 0 || event.target.closest('button, a, input, select')) return;
    // Mouse users can still select and underline the actual quotation.
    if (event.pointerType === 'mouse' && event.target.closest('blockquote')) return;
    gesture.current = { x: event.clientX, y: event.clientY, id: event.pointerId, dragging: false };
  };
  const moveDrag = event => {
    const start = gesture.current;
    if (!start || start.id !== event.pointerId) return;
    const dx = event.clientX - start.x;
    const dy = event.clientY - start.y;
    if (!start.dragging && Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy) * 1.3) {
      start.dragging = true;
      event.currentTarget.setPointerCapture(event.pointerId);
    }
    if (!start.dragging) return;
    event.preventDefault();
    const atBoundary = (index === 0 && dx > 0) || (index === quotes.length - 1 && dx < 0);
    setDragOffset(Math.max(-180, Math.min(180, dx * (atBoundary ? 0.18 : 0.6))));
  };
  const endDrag = event => {
    const start = gesture.current;
    gesture.current = null;
    setDragOffset(0);
    if (!start || start.id !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (event.type !== 'pointercancel' && start.dragging) navigate(evidenceSwipeStep(event.clientX - start.x, event.clientY - start.y));
  };
  const act = callback => { onClose(); callback(); };
  const neighbor = step => {
    const position = index + step;
    const quote = quotes[position];
    if (!quote) return null;
    const origin = sources.find(item => item.id === quote.source_id) || {};
    return <button className={`br-quote-neighbor br-quote-neighbor-${step < 0 ? 'previous' : 'next'}`} onClick={() => navigate(step)} aria-label={t("ui.valueQuotationPassageValue", { value1: step < 0 ? t("ui.previous") : t("ui.next"), value2: position + 1 })}><span className="br-quote-neighbor-label">{step < 0 ? t("ui.previous") : t("ui.next")} · {position + 1} / {quotes.length}</span><span className="br-quote-neighbor-text">{zhText(quote) || quote.quote}</span><span className="br-quote-neighbor-source">{quote.feed || origin.feed}<br />{quote.source_title || origin.title}</span></button>;
  };

  return createPortal(<div className="br-modal-backdrop br-quote-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) { event.preventDefault(); onClose(); } }}>
    <section className={`br-quote-carousel ${quotes.length > 1 ? 'has-neighbors' : ''}`} ref={ref} role="dialog" aria-modal="true" aria-labelledby="br-quote-popover-title">
      {neighbor(-1)}{neighbor(1)}
      <article className={`br-quote-popover ${dragOffset ? 'is-dragging' : ''}`} style={{ '--br-drag-x': `${dragOffset}px` }} onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={endDrag} onPointerCancel={endDrag} onLostPointerCapture={event => {
        // Touch implicitly captures its starting child. Transferring capture to
        // this card emits a bubbling lost event from that child, not a cancel.
        if (event.target === event.currentTarget) { gesture.current = null; setDragOffset(0); }
      }}>
      <header className="br-quote-popover-heading"><div><span>{t("ui.originalQuotation")}{quotes.length > 1 && t("ui.dragLeftOrRightToBrowse")}</span><h2 id="br-quote-popover-title" title={card.context_title || selection.title}>{card.context_title || selection.title || t("ui.evidenceForThisPassage")}</h2></div><button className="br-icon-button" data-close-quote onClick={onClose} aria-label={t("ui.closeQuotations")}><X size={19} /></button></header>
      <div className="br-quote-tools">
        {zhText(card) ? <div className="br-quote-language" role="group" aria-label={t("ui.quotationLanguage")}><button className={!original ? 'is-active' : ''} aria-pressed={!original} onClick={() => setOriginal(false)}>{t("ui.chineseTranslation")}</button><button className={original ? 'is-active' : ''} aria-pressed={original} onClick={() => setOriginal(true)}>{t("ui.originalEnglish")}</button></div> : <span className="br-quote-language-label">{t("ui.original")}</span>}
        <div className="br-quote-mark-tools"><span className="br-quote-mark-hint">{t("ui.selectTextToUnderline")}</span><button disabled={!selectedRange} title={t("ui.selectTextInTheQuotationToUnderline")} onPointerDown={event => event.preventDefault()} onClick={underlineSelection}>{t("ui.underline")}</button><button disabled={!underline} onClick={() => setUnderlines(current => ({ ...current, [underlineKey]: null }))}>{t("ui.clear")}</button></div>
      </div>
      <div className={`br-quote-popover-body ${scrollable && !atEnd ? 'has-more-text' : ''}`} ref={bodyRef} onScroll={measureScroll} tabIndex={0} role="region" aria-label={t("ui.quotationText")}>
        <div className="br-quote-reading" ref={readingRef}>
          {card.brief && <p className="br-quote-context">{card.brief}</p>}
          <blockquote ref={quoteRef} lang={original ? 'en' : undefined}>{underline ? <>{text.slice(0, underline.start)}<mark className="br-quote-underline">{text.slice(underline.start, underline.end)}</mark>{text.slice(underline.end)}</> : text}</blockquote>
        </div>
      </div>
      <div className="br-quote-scroll-hint" aria-hidden={!scrollable}>{scrollable && t("ui.scrollToReadTheFullQuotation")}</div>
      <div className="br-quote-attribution"><div className="br-quote-byline"><strong>{card.feed || source.feed}</strong>{card.speaker && <span>{card.speaker}</span>}</div><span title={card.source_title || source.title}>{card.source_title || source.title}</span></div>
      <footer className="br-quote-popover-footer"><div className="br-quote-links">{onRead && <button className="br-text-button" onClick={() => act(() => onRead(card.source_id))}>{t("ui.readEpisode")}</button>}{episodeId && onListen && <button className="br-text-button" onClick={() => act(() => onListen({ ...card, episode_id: episodeId, original_url: source.original_url || source.url || source.link }))}><Headphones size={14} />{t("ui.listenAt", { time: timeText(card.start) || t("ui.theBeginning") })}</button>}{onSource && <button className="br-text-button" onClick={() => act(() => onSource(card))}>{t("ui.viewInTranscript")}</button>}</div><div className="br-quote-pagination"><button className="br-icon-button" disabled={index === 0} aria-label={t("ui.previousQuotation")} onClick={() => navigate(-1)}><ArrowLeft size={17} /></button><span aria-live="polite">{index + 1} / {quotes.length}</span><button className="br-icon-button" disabled={index === quotes.length - 1} aria-label={t("ui.nextQuotation")} onClick={() => navigate(1)}><ArrowRight size={17} /></button></div></footer>
      </article>
    </section>
  </div>, document.body);
}
