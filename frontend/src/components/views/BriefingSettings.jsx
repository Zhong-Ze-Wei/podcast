import React from 'react';
import BriefingInterests from './BriefingInterests';

export default function BriefingSettings({ interests, autoPeriod, saving, error, onChange, onAutoPeriod, layout, layouts, onLayout, onBack }) {
  return <div className="br-settings">
    <div className="br-settings-intro"><p>决定简报关注什么、何时生成，以及怎样阅读。</p>{onBack && <button className="br-text-button" onClick={onBack}>返回简报</button>}</div>
    <div className="br-settings-grid">
      <BriefingInterests interests={interests} autoPeriod={autoPeriod} saving={saving} error={error} onChange={onChange} onAutoPeriod={onAutoPeriod} />
      <section className="br-settings-card" aria-labelledby="br-style-title"><h2 id="br-style-title">阅读风格</h2><p>同一份内容换一种呈现。切换风格即时生效。</p><div className="br-style-library">{layouts.map(item => <button key={item.id} disabled={saving} aria-pressed={layout === item.id} className={layout === item.id ? 'is-active' : ''} onClick={() => onLayout(item.id)}><strong>{item.name}</strong><span>{item.description}</span></button>)}</div><p className="br-settings-save-note">阅读风格保存到当前账号。PDF 导出继续使用纸面或报刊。</p></section>

    </div>
  </div>;
}
