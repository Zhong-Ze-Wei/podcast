import React from 'react';
import { ChevronDown } from 'lucide-react';
import BriefingInterests from './BriefingInterests';
import BriefingMaterialStyle from './BriefingMaterialStyle';

export default function BriefingSettings({ interests, autoPeriod, saving, error, onChange, onAutoPeriod, layout, layouts, onLayout, materialsLayout, onMaterialsLayout, modeName, prompt, inputDescription, report, period, working, hasMaterials, onGenerate, onBack }) {
  return <div className="br-settings">
    <div className="br-settings-intro"><p>决定简报关注什么、何时生成，以及怎样阅读。</p><button className="br-text-button" onClick={onBack}>返回简报</button></div>
    <div className="br-settings-grid">
      <BriefingInterests interests={interests} autoPeriod={autoPeriod} saving={saving} error={error} onChange={onChange} onAutoPeriod={onAutoPeriod} />
      <section className="br-settings-card" aria-labelledby="br-style-title"><h2 id="br-style-title">阅读风格</h2><p>同一份内容换一种呈现。切换风格即时生效。</p><div className="br-style-library">{layouts.map(item => <button key={item.id} aria-pressed={layout === item.id} className={layout === item.id ? 'is-active' : ''} onClick={() => onLayout(item.id)}><strong>{item.name}</strong><span>{item.description}</span></button>)}</div><p className="br-settings-save-note">选择会保留。PDF 导出继续使用纸面或报刊。</p></section>
      <BriefingMaterialStyle layout={materialsLayout} saving={saving} onChange={onMaterialsLayout} />
      <section className="br-settings-card br-generation-settings"><h2>生成与依据</h2><p>先逐段阅读已有文稿，按关注话题筛选，再生成五种内容模式。原话必须能在对应文稿中逐字找到。</p><p>没有文稿的节目会列在材料清单里，拿到正文后再分析。生成失败时保留之前的报告。</p>
        {prompt && <details className="br-generation-notes"><summary>{modeName} · 提示词与输入 <ChevronDown size={15} /></summary><section><h3>输入内容</h3><p>{inputDescription}</p>{report?.prompt_user_template && <pre>{report.prompt_user_template}</pre>}<h3>{report ? '这份报告使用的提示词' : '当前模式的提示词'}</h3><pre>{prompt}</pre></section></details>}
        <div className="br-settings-run"><span>当前周期：{period?.label || '正在读取'}</span><button className="br-button" disabled={working || saving || !hasMaterials} onClick={() => onGenerate('current')}>生成{modeName}</button><button className="br-button" disabled={working || saving || !hasMaterials} onClick={() => onGenerate('all')}>生成五种模式</button></div>
      </section>
    </div>
  </div>;
}
