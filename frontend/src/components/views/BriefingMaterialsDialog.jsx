import React, { useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { Check, ChevronLeft, ChevronRight, ExternalLink, FileText, Search, Sparkles, X } from 'lucide-react';
import './briefing-materials.css';

function plainDescription(html) {
  return new DOMParser().parseFromString(html || '', 'text/html').body.textContent.replace(/\s+/g, ' ').trim();
}

function EpisodeCard({ material, feeds, CoverComponent, expanded, onExpand, onRead, onOpenEpisode, dateText }) {
  const { t } = useTranslation();
  const label = key => t(`briefingMaterials.${key}`);
  const contentId = `material-${material.episode_id}`;
  const overview = material.analysis_preview || plainDescription(material.description);
  return <article className={`bm-card${expanded ? ' is-open' : ''}`} data-episode-id={material.episode_id}>
    <button className="bm-art" onClick={onExpand} aria-expanded={expanded} aria-controls={contentId} aria-label={`${label('preview')}: ${material.title}`}>
      <span className="bm-art-ambient" aria-hidden="true"><CoverComponent source={material} feeds={feeds} /></span>
      <CoverComponent source={material} feeds={feeds} />
      <span className="bm-art-cue">{expanded ? <X size={14} /> : <ChevronRight size={14} />}</span>
    </button>
    <div className="bm-card-copy">
      <div className="bm-byline"><span>{material.feed}</span><time dateTime={material.published_at}>{dateText(material.published_at)}</time></div>
      <div id={contentId} className={`bm-scroll custom-scrollbar${expanded ? ' is-open' : ''}`} tabIndex={expanded ? 0 : undefined}>
        <h3><button onClick={onExpand} aria-expanded={expanded} aria-controls={contentId}>{material.title}</button></h3>
        {(overview || expanded) && <p className="bm-description">{overview ? <><span className="bm-preview-label">{label(material.analysis_preview ? 'aiOverview' : 'episodeDescription')} · </span>{overview}</> : label('noDescription')}</p>}
        {expanded && material.selected === false && material.relevance_reason && <p className="bm-screening-reason">{material.relevance_reason}</p>}
      </div>
      <div className="bm-status"><span><FileText size={12} />{label(material.has_transcript ? 'transcript' : 'noTranscript')}</span>{material.analysis_status === 'completed' ? <span className="is-complete"><Check size={12} />{label('analyzed')}</span> : material.selected === true && <span className="is-complete">{label('included')}</span>}</div>
      <div className="bm-card-actions">{material.has_transcript && material.source_id && <button className="bm-analysis" onClick={() => onRead(material.source_id)}><Sparkles size={13} />{label(material.analysis_status === 'completed' ? 'readAnalysis' : 'episodeAnalysis')}</button>}<button className="bm-open-episode" onClick={() => onOpenEpisode(material.episode_id)}>{label('openEpisode')}<ExternalLink size={12} /></button></div>
    </div>
  </article>;
}

export default function BriefingMaterialsDialog({ snapshot, feeds, layout = 'gallery', dialogRef, CoverComponent, periodLabel, onClose, onRead, onOpenEpisode }) {
  const { t, i18n } = useTranslation();
  const label = key => t(`briefingMaterials.${key}`);
  const [query, setQuery] = useState('');
  const [expandedId, setExpandedId] = useState(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const dragStart = useRef(null);
  const dragged = useRef(false);
  const galleryRef = useRef(null);
  const previousCardRects = useRef(null);
  const thumbnailsRef = useRef(null);
  const language = i18n.resolvedLanguage || i18n.language;
  const dateText = value => value ? new Intl.DateTimeFormat(language, { month: 'short', day: 'numeric', timeZone: 'Asia/Hong_Kong' }).format(new Date(value)) : '';
  const materials = snapshot.materials || [];
  const search = query.trim().toLocaleLowerCase();
  const episodes = materials.filter(material => !search || `${material.title} ${material.feed}`.toLocaleLowerCase().includes(search));
  const index = Math.min(activeIndex, Math.max(0, episodes.length - 1));
  const move = direction => { setActiveIndex(Math.max(0, Math.min(episodes.length - 1, index + direction))); setExpandedId(null); };
  const jump = nextIndex => { setActiveIndex(nextIndex); setExpandedId(null); };
  useLayoutEffect(() => {
    const strip = thumbnailsRef.current;
    const thumbnail = strip?.children[index];
    if (!thumbnail) return;
    const left = thumbnail.offsetLeft - strip.offsetLeft;
    if (left < strip.scrollLeft || left + thumbnail.offsetWidth > strip.scrollLeft + strip.clientWidth) {
      strip.scrollTo({ left: left - (strip.clientWidth - thumbnail.offsetWidth) / 2, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
    }
  }, [index, query, layout]);
  const openEpisode = id => { onClose(); onOpenEpisode(id); };
  const read = id => { onClose(); onRead(id); };
  const expand = id => {
    if (galleryRef.current) previousCardRects.current = new Map(Array.from(galleryRef.current.children, card => [card.dataset.episodeId, card.getBoundingClientRect()]));
    setExpandedId(current => current === id ? null : id);
  };
  useLayoutEffect(() => {
    const grid = galleryRef.current;
    const previous = previousCardRects.current;
    previousCardRects.current = null;
    if (!grid || !previous || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const cards = Array.from(grid.children);
    const animations = [];
    cards.forEach(card => {
      const before = previous.get(card.dataset.episodeId);
      if (!before) return;
      const after = card.getBoundingClientRect();
      if (before.left === after.left && before.top === after.top && before.width === after.width) return;
      animations.push(card.animate([
        { width: `${before.width}px`, transform: `translate(${before.left - after.left}px, ${before.top - after.top}px)` },
        { width: `${after.width}px`, transform: 'translate(0, 0)' },
      ], { duration: 520, easing: 'cubic-bezier(.22, 1.08, .36, 1)' }));
    });
    const expandedCard = cards.find(card => card.dataset.episodeId === expandedId);
    if (expandedCard) {
      const body = grid.parentElement;
      const cardBottom = expandedCard.offsetTop + expandedCard.offsetHeight;
      if (cardBottom > body.scrollTop + body.clientHeight) body.scrollTo({ top: cardBottom - body.clientHeight + 24, behavior: 'smooth' });
    }
    return () => animations.forEach(animation => animation.cancel());
  }, [expandedId, query, layout]);
  const episodeCard = material => <EpisodeCard key={material.episode_id} material={material} feeds={feeds} CoverComponent={CoverComponent} dateText={dateText} expanded={expandedId === material.episode_id} onExpand={() => expand(material.episode_id)} onRead={read} onOpenEpisode={openEpisode} />;
  const peek = (material, direction) => <button className={`bm-peek ${direction < 0 ? 'is-left' : 'is-right'}`} onClick={() => move(direction)} aria-label={`${label(direction < 0 ? 'previous' : 'next')}: ${material.title}`}><div className="bm-peek-art"><CoverComponent source={material} feeds={feeds} /></div><span>{material.feed}</span><strong>{material.title}</strong></button>;

  return createPortal(<div className="br-modal-backdrop bm-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}><section className={`bm-modal bm-${layout}`} ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="bm-title">
    <header className="bm-heading"><div><span className="bm-period">{periodLabel || snapshot.period.label}</span><h2 id="bm-title">{label('title')}</h2><p>{t('briefingMaterials.count', { total: materials.length, transcripts: materials.filter(material => material.has_transcript).length })}</p></div><button className="bm-close" aria-label={label('close')} onClick={onClose}><X size={19} /></button></header>
    <div className="bm-toolbar"><label className="bm-search"><Search size={15} /><input type="search" value={query} onChange={event => { setQuery(event.target.value); setActiveIndex(0); setExpandedId(null); }} placeholder={label('search')} aria-label={label('search')} /></label>{query && <span className="bm-search-count" role="status">{t('briefingMaterials.results', { count: episodes.length })}</span>}</div>
    <div className="bm-body custom-scrollbar">{!episodes.length ? <div className="bm-empty">{label(materials.length ? 'noResults' : 'empty')}</div> : layout === 'stack' ? <div className="bm-stack-content">
      <div className="bm-deck" tabIndex={0} aria-label={label('dragHint')} onDragStart={event => event.preventDefault()} onKeyDown={event => { if (event.target.closest('input,.bm-scroll.is-open') || !['ArrowLeft', 'ArrowRight'].includes(event.key)) return; event.preventDefault(); move(event.key === 'ArrowLeft' ? -1 : 1); }}
        onPointerDown={event => { dragged.current = false; if (event.button !== 0 || !event.target.closest('.bm-current') || event.target.closest('.bm-card-actions,.bm-scroll.is-open')) return; dragStart.current = { x: event.clientX, y: event.clientY }; event.currentTarget.setPointerCapture(event.pointerId); }}
        onPointerUp={event => { if (!dragStart.current) return; const dx = event.clientX - dragStart.current.x; const dy = event.clientY - dragStart.current.y; dragStart.current = null; if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy)) { dragged.current = true; move(dx > 0 ? -1 : 1); } }}
        onPointerCancel={() => { dragStart.current = null; }} onClickCapture={event => { if (dragged.current) { event.preventDefault(); event.stopPropagation(); dragged.current = false; } }}>
        {index > 0 && peek(episodes[index - 1], -1)}{index + 1 < episodes.length && peek(episodes[index + 1], 1)}<div className="bm-current">{episodeCard(episodes[index])}</div>
      </div><div className="bm-deck-controls"><button onClick={() => move(-1)} disabled={index === 0} aria-label={label('previous')}><ChevronLeft size={18} /></button><span aria-live="polite">{index + 1} / {episodes.length}</span><button onClick={() => move(1)} disabled={index === episodes.length - 1} aria-label={label('next')}><ChevronRight size={18} /></button></div><p className="bm-deck-hint">{label('dragHint')}</p>
    </div> : <div className="bm-gallery-grid" ref={galleryRef}>{episodes.map(episodeCard)}</div>}</div>
    {layout === 'stack' && episodes.length > 0 && <nav className="bm-quicknav" aria-label={label('quickNavigation')}><div className="bm-thumbnails custom-scrollbar" ref={thumbnailsRef} onKeyDown={event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const focusedIndex = Array.from(event.currentTarget.children).indexOf(event.target);
      const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? episodes.length - 1 : Math.max(0, Math.min(episodes.length - 1, focusedIndex + (event.key === 'ArrowLeft' ? -1 : 1)));
      jump(nextIndex);
      event.currentTarget.children[nextIndex].focus({ preventScroll: true });
    }}>{episodes.map((material, position) => <button key={material.episode_id} className={`bm-thumbnail${position === index ? ' is-active' : ''}`} aria-current={position === index ? 'true' : undefined} aria-label={`${position + 1}. ${material.title}`} title={`${material.feed} · ${material.title}`} onClick={() => jump(position)}><CoverComponent source={material} feeds={feeds} /><span aria-hidden="true">{position + 1}</span></button>)}</div></nav>}
  </section></div>, document.body);
}
