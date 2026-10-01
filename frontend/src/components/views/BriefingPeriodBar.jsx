import React, { useEffect, useRef } from 'react';
import { ArrowLeft, ArrowRight, CalendarDays } from 'lucide-react';

export default function BriefingPeriodBar({ period, periods, periodType, loading, onPeriodType, onPeriod, onMaterials, onCurrent }) {
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
  return <section className="br-period-bar" aria-label="报告时间范围">
    <div className="br-period-topline"><div className="br-period-type" role="group" aria-label="报告周期"><button className={periodType === 'week' ? 'is-active' : ''} aria-pressed={periodType === 'week'} disabled={loading} onClick={() => onPeriodType('week')}>周报</button><button className={periodType === 'month' ? 'is-active' : ''} aria-pressed={periodType === 'month'} disabled={loading} onClick={() => onPeriodType('month')}>月报</button></div><button className="br-period-materials" disabled={!period || loading} onClick={onMaterials}><CalendarDays size={15} /><span>{period ? '总计 ' + period.total_count + ' 期' : '正在读取时间范围'}</span><small>{period && '全文 ' + period.transcript_count + ' 期 · ' + (period.selected_count == null ? '待按关注筛选' : '已纳入 ' + period.selected_count + ' 期')}</small></button></div>
    <div className="br-period-timeline"><button className="br-icon-button" disabled={loading || index < 0 || index >= periods.length - 1} aria-label="上一个周期" onClick={() => onPeriod(periods[index + 1])}><ArrowLeft size={17} /></button><nav className="br-period-track" ref={ref} aria-label="选择报告时间范围">{periods.length ? [...periods].reverse().map(item => <button key={item.start} className={item.start === period?.start ? 'is-active' : ''} aria-pressed={item.start === period?.start} disabled={loading} onClick={() => onPeriod(item)}><span>{item.label}</span><small>{item.total_count} 期</small></button>) : <div className="br-period-placeholder">正在整理节目日期</div>}</nav><button className="br-icon-button" disabled={loading || index <= 0} aria-label="下一个周期" onClick={() => onPeriod(periods[index - 1])}><ArrowRight size={17} /></button><button className="br-current-period" disabled={loading} onClick={onCurrent}>{periodType === 'week' ? '本周' : '本月'}</button></div>
  </section>;
}
