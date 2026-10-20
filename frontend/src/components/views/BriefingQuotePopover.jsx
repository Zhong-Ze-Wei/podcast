import { useTranslation } from 'react-i18next';
import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowLeft, ArrowRight, Headphones, LayoutGrid, Minimize2, X } from 'lucide-react';
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

const reducedMotion = () => Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
// 每张散开卡片的固定随机姿态（种子随机，重开弹窗不跳变）
const jitter = (i, salt) => {
  const x = Math.sin(i * 127.1 + salt * 311.7 + 13.37) * 43758.5453;
  return x - Math.floor(x);
};

export default function BriefingQuotePopover({ selection, sources, onClose, onRead, onListen, onSource }) {
  const { t } = useTranslation();
  const [index, setIndex] = useState(() => evidenceIndex(selection.initialIndex || 0, 0, selection.quotes.length));
  const [original, setOriginal] = useState(false);
  const [underlines, setUnderlines] = useState({});
  const [selectedRange, setSelectedRange] = useState(null);
  const [scrollable, setScrollable] = useState(false);
  const [atEnd, setAtEnd] = useState(true);
  const [dragOffset, setDragOffset] = useState(0);
  const [liftOffset, setLiftOffset] = useState(0);
  const [spread, setSpread] = useState(false);
  // 原文依据多为英文逐字引文：打开时对缺 translation 的条目按需补译（后端按引文哈希缓存）
  const [zhMap, setZhMap] = useState({});
  const gesture = useRef(null);
  const ref = useRef(null);
  const cardRef = useRef(null);
  const boardRef = useRef(null);
  const bodyRef = useRef(null);
  const readingRef = useRef(null);
  const quoteRef = useRef(null);
  const pendingExpandRef = useRef(null);
  const gatherTargetRef = useRef(null);
  const indexRef = useRef(index);
  indexRef.current = index;
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
  const spreadMeta = useMemo(() => quotes.map((_, i) => ({
    tilt: (jitter(i, 1) - 0.5) * 10,
    zoom: 0.88 + jitter(i, 2) * 0.26,
    wide: jitter(i, 3) > 0.72,
  })), [quotes]);
  const canSpread = quotes.length > 1;

  useEffect(() => {
    setZhMap({});
    const list = selection.quotes || [];
    const sourceId = list[0] && list[0].source_id;
    // 已有 translation 或本身是中文的都不需要补译；靠近当前阅读位置的排前面，先翻先到
    const need = list
      .filter(item => item.quote && !item.translation && !/[\u4e00-\u9fff]/.test(item.quote))
      .sort((a, b) => Math.abs(list.indexOf(a) - (selection.initialIndex || 0)) - Math.abs(list.indexOf(b) - (selection.initialIndex || 0)));
    if (!sourceId || need.length === 0) return undefined;
    let alive = true;
    (async () => {
      // 后端单次最多接 60 条；再多就分批请求，逐批合并，失败只丢当批
      for (let start = 0; start < need.length; start += 60) {
        try {
          const res = await briefingReportsApi.translateEvidence(sourceId, need.slice(start, start + 60).map(item => ({ id: item.id, quote: item.quote })));
          if (!alive) return;
          const map = res.data?.translations || res.translations || {};
          setZhMap(current => ({ ...current, ...map }));
        } catch { /* 翻译暂不可用时退回原文展示 */ }
      }
    })();
    return () => { alive = false; };
  }, [selection]);

  // 铺开：卡片从主卡位置飞向各自的散布位（FLIP，带错峰）
  const openSpread = () => {
    if (!canSpread || spread) return;
    pendingExpandRef.current = cardRef.current?.getBoundingClientRect() || null;
    setSpread(true);
  };
  // 收拢：所有散卡飞向目标卡位置后卸载，主卡从该位置弹回
  const collapseSpread = focusIndex => {
    if (!spread) return;
    const board = boardRef.current;
    const apply = () => {
      if (focusIndex != null) setIndex(focusIndex);
      setSpread(false);
    };
    if (!board || reducedMotion()) { apply(); return; }
    const target = Math.max(0, Math.min(quotes.length - 1, focusIndex ?? indexRef.current));
    const cards = [...board.querySelectorAll('.br-spread-card')];
    const targetEl = cards[target];
    const targetRect = targetEl?.getBoundingClientRect();
    gatherTargetRef.current = targetRect || null;
    const cx = targetRect ? targetRect.left + targetRect.width / 2 : window.innerWidth / 2;
    const cy = targetRect ? targetRect.top + targetRect.height / 2 : window.innerHeight / 2;
    const animations = cards.map((el, i) => {
      const rect = el.getBoundingClientRect();
      const meta = spreadMeta[i] || { tilt: 0, zoom: 1 };
      const dx = cx - (rect.left + rect.width / 2);
      const dy = cy - (rect.top + rect.height / 2);
      return el.animate([
        { transform: `rotate(${meta.tilt}deg) scale(${meta.zoom})`, opacity: 1 },
        { transform: `translate(${dx}px, ${dy}px) rotate(6deg) scale(.1)`, opacity: 0 },
      ], { duration: 330, delay: Math.min(Math.abs(target - i) * 14, 210), easing: 'cubic-bezier(.55, 0, .7, .4)', fill: 'forwards' }).finished.catch(() => {});
    });
    Promise.all(animations).finally(apply);
  };

  useLayoutEffect(() => {
    if (!spread) return;
    const board = boardRef.current;
    const origin = pendingExpandRef.current;
    pendingExpandRef.current = null;
    if (!board) return;
    board.querySelector('.br-spread-gather')?.focus();
    if (!origin || reducedMotion()) return;
    const ox = origin.left + origin.width / 2;
    const oy = origin.top + origin.height / 2;
    [...board.querySelectorAll('.br-spread-card')].forEach((el, i) => {
      const rect = el.getBoundingClientRect();
      const meta = spreadMeta[i] || { tilt: 0, zoom: 1 };
      const dx = ox - (rect.left + rect.width / 2);
      const dy = oy - (rect.top + rect.height / 2);
      el.animate([
        { transform: `translate(${dx}px, ${dy}px) rotate(9deg) scale(.16)`, opacity: 0 },
        { transform: `rotate(${meta.tilt}deg) scale(${meta.zoom})`, opacity: 1 },
      ], { duration: 560, delay: Math.min(Math.abs(index - i) * 34, 320), easing: 'cubic-bezier(.2, 1.1, .3, 1)' });
    });
  }, [spread]); // eslint-disable-line react-hooks/exhaustive-deps

  useLayoutEffect(() => {
    if (spread) return;
    const target = gatherTargetRef.current;
    gatherTargetRef.current = null;
    const cardEl = cardRef.current;
    if (!target || !cardEl || reducedMotion()) return;
    const rect = cardEl.getBoundingClientRect();
    const dx = (target.left + target.width / 2) - (rect.left + rect.width / 2);
    const dy = (target.top + target.height / 2) - (rect.top + rect.height / 2);
    cardEl.animate([
      { transform: `translate(${dx}px, ${dy}px) translateX(0) scale(.55)`, opacity: .2 },
      { transform: 'translateX(0)', opacity: 1 },
    ], { duration: 280, easing: 'cubic-bezier(.2, .9, .3, 1)' });
  }, [spread]);

  useEffect(() => {
    const before = document.activeElement;    const dialog = ref.current;
    dialog.querySelector('[data-close-quote]')?.focus();
    const onKey = event => {
      if (event.key === 'Escape') { if (spread) collapseSpread(); else onClose(); }
      if (event.key === 'Home' && spread) { event.preventDefault(); boardRef.current?.scrollTo({ top: 0 }); }
      const navigate = !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey;
      if (navigate && event.key === 'ArrowLeft' && quotes.length > 1 && !spread) { event.preventDefault(); setIndex(current => evidenceIndex(current, -1, quotes.length)); }
      if (navigate && event.key === 'ArrowRight' && quotes.length > 1 && !spread) { event.preventDefault(); setIndex(current => evidenceIndex(current, 1, quotes.length)); }
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
  }, [onClose, quotes.length, spread]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    setOriginal(false);
    setDragOffset(0);
    setLiftOffset(0);
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
    gesture.current = { x: event.clientX, y: event.clientY, id: event.pointerId, dragging: false, lifting: false };
  };
  const moveDrag = event => {
    const start = gesture.current;
    if (!start || start.id !== event.pointerId) return;
    const dx = event.clientX - start.x;
    const dy = event.clientY - start.y;
    if (!start.dragging && !start.lifting && dy < -12 && Math.abs(dy) > Math.abs(dx) * 1.2 && canSpread && !spread) {
      start.lifting = true;                                  // 上滑：提起整叠卡片准备铺开
      event.currentTarget.setPointerCapture(event.pointerId);
    } else if (!start.dragging && !start.lifting && Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy) * 1.3) {
      start.dragging = true;
      event.currentTarget.setPointerCapture(event.pointerId);
    }
    if (start.lifting && !spread) {
      event.preventDefault();
      setLiftOffset(Math.max(-110, Math.min(6, dy * 0.55)));
      return;
    }
    if (!start.dragging) return;
    event.preventDefault();
    const atBoundary = (index === 0 && dx > 0) || (index === quotes.length - 1 && dx < 0);
    setDragOffset(Math.max(-180, Math.min(180, dx * (atBoundary ? 0.18 : 0.6))));
  };
  const endDrag = event => {
    const start = gesture.current;
    gesture.current = null;
    const dy = start ? event.clientY - start.y : 0;
    setDragOffset(0);
    setLiftOffset(0);
    if (!start || start.id !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (event.type === 'pointercancel') return;
    if (start.lifting && dy < -56) { openSpread(); return; }  // 上滑到位：铺开整叠
    if (start.dragging) navigate(evidenceSwipeStep(event.clientX - start.x, event.clientY - start.y));
  };
  const act = callback => { onClose(); callback(); };
  const neighbor = step => {
    const position = index + step;
    const quote = quotes[position];
    if (!quote) return null;
    const origin = sources.find(item => item.id === quote.source_id) || {};
    return <button className={`br-quote-neighbor br-quote-neighbor-${step < 0 ? 'previous' : 'next'}`} onClick={() => navigate(step)} aria-label={t("ui.valueQuotationPassageValue", { value1: step < 0 ? t("ui.previous") : t("ui.next"), value2: position + 1 })}><span className="br-quote-neighbor-label">{step < 0 ? t("ui.previous") : t("ui.next")} · {position + 1} / {quotes.length}</span><span className="br-quote-neighbor-text">{zhText(quote) || quote.quote}</span><span className="br-quote-neighbor-source">{quote.feed || origin.feed}<br />{quote.source_title || origin.title}</span></button>;
  };

  return createPortal(<div className="br-modal-backdrop br-quote-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) { event.preventDefault(); if (spread) collapseSpread(); else onClose(); } }}>
    <section className={`br-quote-carousel ${quotes.length > 1 ? 'has-neighbors' : ''} ${spread ? 'is-spread' : ''}`} ref={ref} role="dialog" aria-modal="true" aria-labelledby="br-quote-popover-title">
      {neighbor(-1)}{neighbor(1)}
      <article className={`br-quote-popover ${(dragOffset || liftOffset) ? 'is-dragging' : ''}`} ref={cardRef} style={{ '--br-drag-x': `${dragOffset}px`, '--br-lift-y': `${liftOffset}px` }} onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={endDrag} onPointerCancel={endDrag} onLostPointerCapture={event => {
        // Touch implicitly captures its starting child. Transferring capture to
        // this card emits a bubbling lost event from that child, not a cancel.
        if (event.target === event.currentTarget) { gesture.current = null; setDragOffset(0); setLiftOffset(0); }
      }}>
      <header className="br-quote-popover-heading"><div><span>{t("ui.originalQuotation")}{quotes.length > 1 && t("ui.dragLeftOrRightToBrowse")}{canSpread && t("ui.swipeUpToSpread")}</span><h2 id="br-quote-popover-title" title={card.context_title || selection.title}>{card.context_title || selection.title || t("ui.evidenceForThisPassage")}</h2></div><button className="br-icon-button" data-close-quote onClick={onClose} aria-label={t("ui.closeQuotations")}><X size={19} /></button></header>
      <div className="br-quote-tools">
        {canSpread && <button className="br-quote-spread-trigger" onClick={openSpread} title={t("ui.spreadReview")}><LayoutGrid size={15} />{t("ui.spreadReview")}</button>}
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
      {spread && <div className="br-spread-board custom-scrollbar" ref={boardRef} role="group" aria-label={t("ui.spreadReview")}>
        <div className="br-spread-toolbar">
          <div className="br-spread-caption"><strong>{t("ui.spreadReview")}</strong><span>{t("ui.spreadCardHint")}</span></div>
          <button className="br-button br-spread-gather" onClick={() => collapseSpread(index)}><Minimize2 size={15} />{t("ui.gatherCards")}</button>
        </div>
        {quotes.map((item, i) => {
          const meta = spreadMeta[i] || { tilt: 0, zoom: 1 };
          const origin = sources.find(entry => entry.id === item.source_id) || {};
          return <button key={`${item.id || 'q'}:${i}`} className={`br-spread-card ${meta.wide ? 'is-wide' : ''}`} style={{ '--tilt': `${meta.tilt.toFixed(2)}deg`, '--zoom': meta.zoom.toFixed(3) }} onClick={() => collapseSpread(i)}>
            <span className="br-spread-source"><strong>{item.feed || origin.feed}</strong>{(item.source_title || origin.title) && <em>{item.source_title || origin.title}</em>}</span>
            <p className="br-spread-text">{zhText(item) || item.quote}</p>
            <span className="br-spread-index" aria-hidden="true">{i + 1}</span>
          </button>;
        })}
      </div>}
    </section>
  </div>, document.body);
}
