import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowLeft, ArrowRight, Headphones, X } from 'lucide-react';

function timeText(value) {
  if (value == null || !Number.isFinite(Number(value))) return '';
  const seconds = Math.floor(Number(value));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds % 3600 / 60);
  return (hours ? hours + ':' + String(minutes).padStart(2, '0') : minutes) + ':' + String(seconds % 60).padStart(2, '0');
}

export default function BriefingQuotePopover({ selection, sources, onClose, onRead, onListen, onSource }) {
  const [index, setIndex] = useState(0);
  const [original, setOriginal] = useState(false);
  const ref = useRef(null);
  const bodyRef = useRef(null);
  const quotes = selection.quotes;
  const card = quotes[index];
  const source = sources.find(item => item.id === card.source_id) || {};
  const episodeId = card.episode_id || source.episode_id;

  useEffect(() => {
    const before = document.activeElement;
    const dialog = ref.current;
    dialog.querySelector('button')?.focus();
    const onKey = event => {
      if (event.key === 'Escape') onClose();
      if (event.key === 'ArrowLeft' && quotes.length > 1) { event.preventDefault(); setIndex(current => (current - 1 + quotes.length) % quotes.length); }
      if (event.key === 'ArrowRight' && quotes.length > 1) { event.preventDefault(); setIndex(current => (current + 1) % quotes.length); }
      if (event.key !== 'Tab') return;
      const elements = [...dialog.querySelectorAll('button:not([disabled]), a[href]')];
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
    bodyRef.current.scrollTop = 0;
    if (!ref.current.contains(document.activeElement)) ref.current.querySelector('button')?.focus();
  }, [index]);

  const move = event => {
    if (event.pointerType !== 'mouse' || !window.matchMedia('(hover: hover) and (pointer: fine)').matches || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const bounds = ref.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    const y = Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height));
    ref.current.style.setProperty('--br-light-x', x * 100 + '%');
    ref.current.style.setProperty('--br-light-y', y * 100 + '%');
    ref.current.style.setProperty('--br-tilt-x', (0.5 - y) * 1.5 + 'deg');
    ref.current.style.setProperty('--br-tilt-y', (x - 0.5) * 1.5 + 'deg');
  };
  const reset = () => { ref.current.style.setProperty('--br-tilt-x', '0deg'); ref.current.style.setProperty('--br-tilt-y', '0deg'); };
  const act = callback => { onClose(); callback(); };

  return createPortal(<div className="br-modal-backdrop br-quote-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="br-quote-popover" ref={ref} role="dialog" aria-modal="true" aria-labelledby="br-quote-popover-title" onPointerMove={move} onPointerLeave={reset}>
      <header className="br-quote-popover-heading"><div><span>节目原话</span><h2 id="br-quote-popover-title">{selection.title || '这段内容的依据'}</h2></div><button className="br-icon-button" onClick={onClose} aria-label="关闭原话窗口"><X size={19} /></button></header>
      <div className="br-quote-popover-body" ref={bodyRef}>
        {card.brief && <p className="br-quote-context">{card.brief}</p>}
        {card.translation && <div className="br-quote-language" role="group" aria-label="原话语言"><button className={!original ? 'is-active' : ''} aria-pressed={!original} onClick={() => setOriginal(false)}>中文译文</button><button className={original ? 'is-active' : ''} aria-pressed={original} onClick={() => setOriginal(true)}>英文原话</button></div>}
        <blockquote lang={original ? 'en' : undefined}>{original ? card.quote : card.translation || card.quote}</blockquote>
        <div className="br-quote-attribution"><strong>{card.feed || source.feed}</strong>{card.speaker && <span>{card.speaker}</span>}<span>{card.source_title || source.title}</span></div>
      </div>
      <footer className="br-quote-popover-footer"><div className="br-quote-links"><button className="br-text-button" onClick={() => act(() => onRead(card.source_id))}>读这期</button>{episodeId && <button className="br-text-button" onClick={() => act(() => onListen({ ...card, episode_id: episodeId, original_url: source.original_url || source.url || source.link }))}><Headphones size={14} />从 {timeText(card.start) || '开头'} 听</button>}<button className="br-text-button" onClick={() => act(() => onSource(card))}>在文稿中查看</button></div>{quotes.length > 1 && <div className="br-quote-pagination"><button className="br-icon-button" aria-label="上一段原话" onClick={() => setIndex(current => (current - 1 + quotes.length) % quotes.length)}><ArrowLeft size={17} /></button><span aria-live="polite">{index + 1} / {quotes.length}</span><button className="br-icon-button" aria-label="下一段原话" onClick={() => setIndex(current => (current + 1) % quotes.length)}><ArrowRight size={17} /></button></div>}</footer>
    </section>
  </div>, document.body);
}
