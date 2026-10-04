// This page is self-contained: all demonstration content stays in the browser.
const text = (zh, en) => ({ zh, en });
const phrases = {
  week: text('2026.09.21 — 09.27 / 周报', '2026.09.21 — 09.27 / WEEKLY'),
  month: text('2026.09 / 月报', '2026.09 / MONTHLY'),
  reuse: text('复用 2 份已保存的单篇分析', 'Reusing 2 saved episode analyses'),
  evidence: text('原话依据 ↗', 'Source quotation ↗'),
  save: text('收藏这个观点', 'Save this idea'),
  unsave: text('取消收藏', 'Unsave this idea'),
  kind: text('演示提要', 'SAMPLE TAKEAWAY'),
  concepts: text('演示概念与方法', 'SAMPLE CONCEPT'),
  connections: text('两个节目的观点', 'TWO EPISODE PERSPECTIVES'),
  resources: text('演示文稿与资料', 'SAMPLE RESOURCE'),
  quotes: text('演示原话', 'SAMPLE QUOTATION'),
};
const sources = [
  text('工程下午茶 · 把 AI 放进工作流', 'Engineering Tea · AI in the workflow'),
  text('组织与技术 · 谁来做最后的判断', 'Work & Technology · Who makes the judgment'),
  text('工程下午茶 · 好问题的形状', 'Engineering Tea · The shape of a good question'),
];
const quotations = [
  { context: text('工具与判断', 'Tools and judgment'), source: 0, quote: text('工具可以帮我们更快地完成一件事，但决定这件事值不值得做，仍然需要人来判断。', 'A tool can help us do something faster. Deciding whether it is worth doing still requires human judgment.') },
  { context: text('先提速，还是先改流程？', 'Speed up, or rethink the workflow?'), source: 1, quote: text('如果原来的流程本身没有意义，把它加速十倍，也不一定会得到更好的结果。', 'If the original workflow has little value, making it ten times faster may not lead to a better result.') },
  { context: text('先把问题说清楚', 'Clarify the question first'), source: 2, quote: text('开始之前，先约定一个能被检验的问题。否则我们很容易把漂亮的输出，当成真正的进展。', 'Start with a question that can be tested. Otherwise, it is easy to mistake a polished output for real progress.') },
];
const cards = {
  core: [
    { title: text('AI 的价值，藏在具体工作流里', 'The value of AI lives in the workflow'), body: text('先确定工具要解决的具体问题，再决定它应该放在哪个环节。产出变快，不等于判断可以被省略。', 'Identify the problem before choosing where a tool belongs. Faster output does not remove the need for judgment.'), source: 0, evidence: 0 },
    { title: text('先定义好问题，再让模型行动', 'Define the question before the model acts'), body: text('明确目标、条件和评判方式，才能判断一次尝试是否带来了进展。保留限制条件，比只记住结论更有用。', 'Set the goal, conditions and evaluation criteria so that progress can be assessed. Keep the limitations alongside the conclusion.'), source: 2, evidence: 2 },
  ],
  quotes: [
    { title: text('「决定值不值得做，仍然需要人。」', '“Deciding whether it is worth doing still requires human judgment.”'), body: text('讨论 AI 工具的边界时，把执行速度与人的价值判断区分开。点开依据，可以读到完整表述。', 'Separate execution speed from human judgment when discussing the boundaries of AI tools. Open the source to read the complete sample quotation.'), source: 0, evidence: 0 },
    { title: text('「加速十倍，也不一定更好。」', '“Ten times faster may not lead to a better result.”'), body: text('从组织与流程的角度提出另一种观察：改进已有环节之前，先问这条流程本身是否有意义。', 'A perspective on organizations and processes: before improving a step, ask whether the workflow itself is useful.'), source: 1, evidence: 1 },
  ],
  connections: [
    { title: text('共同点：把判断留在人手中', 'Common ground: keep judgment with people'), body: text('两期演示节目都把工具能力与人的判断分开。共同之处是：效率可以提升，但目标和价值仍需要被讨论。', 'Both sample episodes distinguish a tool’s capabilities from human judgment. Efficiency can improve, while goals and value still need discussion.'), source: 0, evidence: 0 },
    { title: text('分歧：先提速，还是先改流程？', 'Difference: speed up, or rethink the workflow?'), body: text('工程视角关注先把工具放进现有工作流；组织视角更强调先改变工作方式。面对同一个问题，行动顺序不同。', 'The engineering perspective starts by adding tools to an existing workflow. The organizational perspective starts by changing the way work is done.'), source: 1, evidence: 1 },
  ],
  concepts: [
    { title: text('Human-in-the-loop · 人在回路中', 'Human-in-the-loop'), body: text('把人的判断与反馈留在关键环节。这里强调的是谁设定目标、谁检查结果，以及谁对最终决定负责。', 'Keep human judgment and feedback at key steps: who sets the goal, checks the result and owns the final decision?'), source: 0, evidence: 0 },
    { title: text('可检验的问题', 'A testable question'), body: text('先写清楚问题、成功标准和适用条件，再观察模型的回答。这是一种让讨论和实验更具体的方法。', 'Write down the question, success criteria and applicable conditions before evaluating an answer. It makes discussions and experiments more concrete.'), source: 2, evidence: 2 },
  ],
  resources: [
    { title: text('《工作流观察笔记》', 'Workflow observation notes'), body: text('演示资料：记录一个工具介入前后，任务、决策与反馈如何变化。与“先提速还是先改流程”的讨论相呼应。', 'Sample material: notes on how tasks, decisions and feedback change when a tool enters a workflow.'), source: 1, evidence: 1 },
    { title: text('《好问题的检查清单》', 'A checklist for good questions'), body: text('演示资料：用目标、条件、评价方式三个维度检查问题。资料与提及它的节目出处一起保留。', 'Sample material: examine a question through its goal, conditions and evaluation criteria. Keep the resource together with its episode source.'), source: 2, evidence: 2 },
  ],
};
const screenshots = {
  briefing: { path: './assets/briefing.jpg', caption: text('五个内容栏目，同一份已保存报告。阅读风格随时可换。', 'Five content sections, saved reports and reading layouts you can change at any time.'), alt: text('AI 简报的纸面阅读界面，包含观点、原话依据和出处', 'Paper-style AI briefing with insights, evidence and sources') },
  library: { path: './assets/library.jpg', caption: text('订阅、最近更新与工作台，放在一个熟悉的内容库里。', 'Subscriptions, recent updates and a workbench in one familiar library.'), alt: text('传统模式的订阅内容库，显示节目卡片与最近更新入口', 'Traditional subscription library with episode covers and recent updates') },
  analysis: { path: './assets/analysis.jpg', caption: text('先保存单篇的完整解读，再让周报与月报继续复用。', 'Save a full episode analysis first, then reuse it in weekly and monthly briefings.'), alt: text('单篇节目的 AI 解读，包含核心摘要、议题和原话', 'An episode analysis with its summary, topics and quotations') },
};
let language = 'zh', mode = 'core', period = 'week', shot = 'briefing', quoteIndex = 0;
const saved = new Set();
const $ = selector => document.querySelector(selector);
const localized = value => value[language];
const staticCopy = [...document.querySelectorAll('[data-en]')].map(element => ({ element, zh: element.textContent, en: element.dataset.en }));
const staticAttributes = ['aria-label', 'alt'].flatMap(attribute => [...document.querySelectorAll('[data-en-' + attribute + ']')].map(element => ({ element, attribute, zh: element.getAttribute(attribute), en: element.getAttribute('data-en-' + attribute) })));

function makeElement(tag, className, content) {
  const element = document.createElement(tag);
  element.className = className;
  if (content !== undefined) element.textContent = content;
  return element;
}
function renderCards() {
  const panel = $('#demo-panel');
  panel.replaceChildren();
  panel.setAttribute('aria-labelledby', 'tab-' + mode);
  cards[mode].forEach((card, index) => {
    const key = mode + '-' + index;
    const article = makeElement('article', 'demo-card');
    article.append(makeElement('span', 'card-kind', localized(phrases[mode] || phrases.kind)));
    article.append(makeElement('h4', '', localized(card.title)));
    article.append(makeElement('p', '', localized(card.body)));
    const evidence = makeElement('button', 'card-evidence', localized(phrases.evidence));
    evidence.type = 'button';
    evidence.addEventListener('click', () => { quoteIndex = card.evidence; renderQuote(); $('#quote-dialog').showModal(); });
    article.append(evidence);
    const footer = makeElement('footer', 'card-footer');
    footer.append(makeElement('span', '', localized(sources[card.source])));
    const favorite = makeElement('button', 'card-save', saved.has(key) ? '♥' : '♡');
    favorite.type = 'button';
    favorite.setAttribute('aria-label', localized(saved.has(key) ? phrases.unsave : phrases.save));
    favorite.setAttribute('aria-pressed', String(saved.has(key)));
    favorite.addEventListener('click', () => {
      if (saved.has(key)) saved.delete(key); else saved.add(key);
      favorite.textContent = saved.has(key) ? '♥' : '♡';
      favorite.setAttribute('aria-pressed', String(saved.has(key)));
      favorite.setAttribute('aria-label', localized(saved.has(key) ? phrases.unsave : phrases.save));
      $('#saved-count').textContent = saved.size;
    });
    footer.append(favorite);
    article.append(footer);
    panel.append(article);
  });
}
function renderPeriod() {
  $('#demo-period-label').textContent = localized(phrases[period]);
  $('#demo-reuse-label').textContent = localized(phrases.reuse);
  document.querySelectorAll('[data-period]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.period === period)));
}
function activateMode(next) {
  mode = next;
  document.querySelectorAll('[data-mode]').forEach(button => {
    const active = button.dataset.mode === mode;
    button.setAttribute('aria-selected', String(active));
    button.tabIndex = active ? 0 : -1;
  });
  renderCards();
}
function renderShot() {
  const current = screenshots[shot];
  $('#gallery-image').src = current.path;
  $('#gallery-image').alt = localized(current.alt);
  $('#gallery-description').textContent = localized(current.caption);
  $('#gallery-panel').setAttribute('aria-labelledby', 'shot-' + shot);
  document.querySelectorAll('[data-shot]').forEach(button => {
    const active = button.dataset.shot === shot;
    button.setAttribute('aria-selected', String(active));
    button.tabIndex = active ? 0 : -1;
  });
}
function renderQuote() {
  const current = quotations[quoteIndex];
  $('#quote-context').textContent = localized(current.context);
  $('#quote-text').textContent = localized(current.quote);
  $('#quote-source').textContent = localized(sources[current.source]);
  $('#quote-count').textContent = (quoteIndex + 1) + ' / ' + quotations.length;
  const previous = $('.quote-neighbor-prev'), next = $('.quote-neighbor-next');
  previous.disabled = $('#quote-previous').disabled = quoteIndex === 0;
  next.disabled = $('#quote-next').disabled = quoteIndex === quotations.length - 1;
  previous.querySelector('.neighbor-text').textContent = quoteIndex > 0 ? localized(quotations[quoteIndex - 1].quote) : '';
  next.querySelector('.neighbor-text').textContent = quoteIndex + 1 < quotations.length ? localized(quotations[quoteIndex + 1].quote) : '';
}
function moveQuote(direction) {
  const next = quoteIndex + direction;
  if (next < 0 || next >= quotations.length) return;
  quoteIndex = next;
  renderQuote();
}
function changeLanguage() {
  language = language === 'zh' ? 'en' : 'zh';
  document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
  document.title = language === 'zh' ? 'PodMaster — 听见观点，读懂它们的关系' : 'PodMaster — Listen closely. Connect the dots.';
  staticCopy.forEach(copy => { copy.element.textContent = copy[language]; });
  staticAttributes.forEach(copy => copy.element.setAttribute(copy.attribute, copy[language]));
  $('#language-switch').textContent = language === 'zh' ? 'EN' : '中文';
  $('#language-switch').setAttribute('aria-label', language === 'zh' ? 'Switch to English' : '切换到中文');
  renderCards(); renderPeriod(); renderShot(); renderQuote();
}
function tabKeyboard(event, buttons, activate) {
  const current = buttons.indexOf(document.activeElement);
  let next;
  if (event.key === 'ArrowRight') next = (current + 1) % buttons.length;
  if (event.key === 'ArrowLeft') next = (current - 1 + buttons.length) % buttons.length;
  if (event.key === 'Home') next = 0;
  if (event.key === 'End') next = buttons.length - 1;
  if (next === undefined) return;
  event.preventDefault();
  activate(buttons[next]); buttons[next].focus();
}
$('#language-switch').addEventListener('click', changeLanguage);
$('#motion-switch').addEventListener('click', event => {
  const paused = document.documentElement.classList.toggle('motion-paused');
  event.currentTarget.setAttribute('aria-pressed', String(paused));
  event.currentTarget.querySelector('.motion-icon').textContent = paused ? '▷' : 'Ⅱ';
});
const modeButtons = [...document.querySelectorAll('[data-mode]')];
modeButtons.forEach(button => button.addEventListener('click', () => activateMode(button.dataset.mode)));
$('.demo-tabs').addEventListener('keydown', event => tabKeyboard(event, modeButtons, button => activateMode(button.dataset.mode)));
document.querySelectorAll('[data-period]').forEach(button => button.addEventListener('click', () => { period = button.dataset.period; renderPeriod(); }));
$('#demo-layout').addEventListener('change', event => { $('#demo-panel').className = 'demo-panel layout-' + event.target.value; });
const shotButtons = [...document.querySelectorAll('[data-shot]')];
shotButtons.forEach(button => button.addEventListener('click', () => { shot = button.dataset.shot; renderShot(); }));
$('.gallery-tabs').addEventListener('keydown', event => tabKeyboard(event, shotButtons, button => { shot = button.dataset.shot; renderShot(); }));
$('#expand-screenshot').addEventListener('click', () => {
  const current = screenshots[shot];
  $('#large-screenshot').src = current.path;
  $('#large-screenshot').alt = localized(current.alt);
  $('#large-caption').textContent = localized(current.caption);
  $('#screenshot-dialog').showModal();
});
document.querySelectorAll('dialog').forEach(dialog => {
  dialog.querySelector('.dialog-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
});
$('.quote-neighbor-prev').addEventListener('click', () => moveQuote(-1));
$('.quote-neighbor-next').addEventListener('click', () => moveQuote(1));
$('#quote-previous').addEventListener('click', () => moveQuote(-1));
$('#quote-next').addEventListener('click', () => moveQuote(1));
$('#quote-dialog').addEventListener('keydown', event => {
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); moveQuote(event.key === 'ArrowLeft' ? -1 : 1); }
});
let dragStart;
$('#quote-card').addEventListener('pointerdown', event => {
  if (!event.isPrimary || event.button !== 0) return;
  dragStart = { x: event.clientX, y: event.clientY, id: event.pointerId };
  event.currentTarget.setPointerCapture(event.pointerId);
});
$('#quote-card').addEventListener('pointerup', event => {
  if (!dragStart || event.pointerId !== dragStart.id) return;
  const horizontal = event.clientX - dragStart.x, vertical = event.clientY - dragStart.y;
  if (Math.abs(horizontal) > 50 && Math.abs(horizontal) > Math.abs(vertical) * 1.3) moveQuote(horizontal < 0 ? 1 : -1);
  dragStart = null;
});
$('#quote-card').addEventListener('pointercancel', () => { dragStart = null; });
renderCards(); renderPeriod(); renderShot(); renderQuote();
document.documentElement.classList.add('js');
const reveals = new IntersectionObserver(entries => entries.forEach(entry => {
  if (entry.isIntersecting) { entry.target.classList.add('is-visible'); reveals.unobserve(entry.target); }
}), { threshold: .08 });
document.querySelectorAll('.reveal').forEach(element => reveals.observe(element));
