import React, { useState } from 'react';
import { Check, Loader2, Plus, X } from 'lucide-react';

export default function BriefingInterests({ interests, autoPeriod, saving, error, onChange, onAutoPeriod }) {
  const [label, setLabel] = useState('');
  const add = event => {
    event.preventDefault();
    const nextLabel = label.trim();
    if (!nextLabel) return;
    const existing = interests.find(item => item.label.toLowerCase() === nextLabel.toLowerCase());
    if (saving || (!existing && interests.length >= 12)) return;
    onChange(existing ? interests.map(item => item === existing ? { ...item, enabled: true } : item) : [...interests, { label: nextLabel, enabled: true }]);
    setLabel('');
  };
  return <section className="br-settings-card br-interests-settings" aria-labelledby="br-interest-title">
    <div className="br-interests-heading"><h2 id="br-interest-title">关注的话题</h2>{saving && <Loader2 size={14} className="br-spinning" aria-label="正在保存关注" />}</div><div className="br-interest-tags">{interests.map(item => <div className={item.enabled ? 'is-enabled' : ''} key={item.label}><button className="br-interest-toggle" disabled={saving} aria-pressed={item.enabled} onClick={() => onChange(interests.map(current => current.label === item.label ? { ...current, enabled: !current.enabled } : current))}>{item.enabled && <Check size={13} />}{item.label}</button><button className="br-interest-remove" disabled={saving} aria-label={'删除关注话题 ' + item.label} onClick={() => onChange(interests.filter(current => current.label !== item.label))}><X size={13} /></button></div>)}</div>
    <form className="br-interest-add" onSubmit={add}><input aria-label="添加关注话题" placeholder="添加话题，例如 LLM、机器人" maxLength={30} value={label} onChange={event => setLabel(event.target.value)} /><button className="br-icon-button" type="submit" disabled={saving || !label.trim() || interests.length >= 12} aria-label="添加话题"><Plus size={18} /></button></form>
    <p>先读正文，筛选与话题相关的节目，再生成这个周期的报告。关闭全部话题则分析所有有文稿的节目。</p>
    <label className="br-auto-period">自动生成<select aria-label="自动生成报告" value={autoPeriod || ''} disabled={saving} onChange={event => onAutoPeriod(event.target.value || null)}><option value="">关闭</option><option value="week">每周</option><option value="month">每月</option></select></label><p className="br-auto-period-note">{autoPeriod === 'week' ? '每周一 00:05 后生成上周报告（香港时间）。' : autoPeriod === 'month' ? '每月1日 00:05 后生成上月报告（香港时间）。' : '周期结束后按关注话题生成五种内容模式。'}</p>
    {error && <p className="br-interest-error" role="alert">{error}</p>}
    <span className="br-settings-save-note">{saving ? '正在保存…' : '修改后自动保存，下一次生成时使用。'}</span>
  </section>;
}
