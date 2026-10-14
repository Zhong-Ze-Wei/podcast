import { formatPeriodLabel } from '../../utils/localization';
import { useTranslation } from 'react-i18next';
import React, { useEffect, useRef } from 'react';
import { ArrowLeft, ArrowRight, CalendarDays } from 'lucide-react';

export default function BriefingPeriodBar({ period, periods, periodType, loading, onPeriodType, onPeriod, onMaterials, onCurrent }) {
  const { t, i18n } = useTranslation();
  const ref = useRef(null);
  const index = periods.findIndex(item => item.start === period?.start);
  useEffect(() => { ref.current?.querySelector('[aria-pressed="true"]')?.scrollIntoView({ block: 'nearest', inline: 'center', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); }, [period?.start]);
  useEffect(() => {
    const track = ref.current;
    const slide = event => {
      if (track.scrollWidth <= track.clientWidth || Math.abs(event.deltaX) >= Math.abs(event.deltaY)) return;
      if ((event.deltaY < 0 && track.scrollLeft <= 0) || (event.deltaY > 0 && track.scrollLeft >= track.scrollWidth - track.clientWidth - 1)) return;
      event.preventDefault();
      track.scrollLeft += event.deltaY;
    };
    track.addEventListener('wheel', slide, { passive: false });
    return () => track.removeEventListener('wheel', slide);
  }, []);
  return <section className="br-period-bar" aria-label={t("ui.reportDateRange")}>
    <div className="br-period-topline"><div className="br-period-type" role="group" aria-label={t("ui.reportPeriod")}><button className={periodType === 'week' ? 'is-active' : ''} aria-pressed={periodType === 'week'} disabled={loading} onClick={() => onPeriodType('week')}>{t("ui.weekly")}</button><button className={periodType === 'month' ? 'is-active' : ''} aria-pressed={periodType === 'month'} disabled={loading} onClick={() => onPeriodType('month')}>{t("ui.monthly")}</button></div><button className="br-period-materials" disabled={!period || loading} onClick={onMaterials}><CalendarDays size={15} /><span>{period ? t("ui.episodeCount", { count: period.total_count }) : t("ui.loadingDateRanges")}</span><small>{period && t("ui.transcriptCount", { count: period.transcript_count }) + (period.selected_count == null ? t("ui.awaitingInterestScreening") : t("ui.includedCount", { count: period.selected_count }))}</small></button></div>
    <div className="br-period-timeline"><button className="br-icon-button" disabled={loading || index < 0 || index >= periods.length - 1} aria-label={t("ui.previousPeriod")} onClick={() => onPeriod(periods[index + 1])}><ArrowLeft size={17} /></button><nav className="br-period-track" ref={ref} aria-label={t("ui.chooseReportDates")}>{periods.length ? [...periods].reverse().map(item => <button key={item.start} className={item.start === period?.start ? 'is-active' : ''} aria-pressed={item.start === period?.start} disabled={loading} onClick={() => onPeriod(item)}><span>{formatPeriodLabel(item, i18n.resolvedLanguage)}</span><small>{item.total_count} {t("ui.episodes")}</small></button>) : <div className="br-period-placeholder">{t("ui.loadingEpisodeDates")}</div>}</nav><button className="br-icon-button" disabled={loading || index <= 0} aria-label={t("ui.nextPeriod")} onClick={() => onPeriod(periods[index - 1])}><ArrowRight size={17} /></button><button className="br-current-period" disabled={loading} onClick={onCurrent}>{periodType === 'week' ? t("ui.thisWeek") : t("ui.thisMonth")}</button></div>
  </section>;
}
