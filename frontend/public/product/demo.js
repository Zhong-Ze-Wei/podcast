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
  listening: { path: './assets/listening.jpg', caption: text('边听边读文稿，底部播放器随时调整进度与音量。', 'Listen alongside the transcript, with seeking, skip controls and volume in the bottom player.'), alt: text('传统模式的节目文稿和底部播放器', 'Traditional episode transcript and bottom audio player') },
  briefing: { path: './assets/briefing.jpg', caption: text('五个内容栏目，同一份已保存报告。阅读风格随时可换。', 'Five content sections, saved reports and reading layouts you can change at any time.'), alt: text('AI 简报的纸面阅读界面，包含观点、原话依据和出处', 'Paper-style AI briefing with insights, evidence and sources') },
  library: { path: './assets/library.jpg', caption: text('订阅、最近更新与工作台，放在一个熟悉的内容库里。', 'Subscriptions, recent updates and a workbench in one familiar library.'), alt: text('传统模式的订阅内容库，显示节目卡片与最近更新入口', 'Traditional subscription library with episode covers and recent updates') },
  analysis: { path: './assets/analysis.jpg', caption: text('先保存单篇的完整解读，再让周报与月报继续复用。', 'Save a full episode analysis first, then reuse it in weekly and monthly briefings.'), alt: text('单篇节目的 AI 解读，包含核心摘要、议题和原话', 'An episode analysis with its summary, topics and quotations') },
};
const exampleUrls = { rss: 'https://podcasts.example.com/feed.xml', youtube: 'https://www.youtube.com/@demo-channel', bilibili: 'https://space.bilibili.com/12345678' };
const podcasts = [
  { name: text('工程下午茶', 'Engineering Tea'), type: 'RSS', cover: 'cover-work.svg', unread: false, episodes: [
    { title: text('把 AI 放进工作流', 'AI in the workflow'), duration: 3610, days: 2, transcript: [text('主持人：一个新工具出现以后，我们应该先从哪里开始？', 'Host: Where should we start when a new tool arrives?'), text('嘉宾：先看清楚具体问题，再决定把工具放在哪个环节。不是每个任务都需要同一种做法。', 'Guest: Understand the problem before deciding where the tool belongs. Different tasks need different approaches.'), text('主持人：所以提高效率只是第一步，后面还需要判断结果是否有用。', 'Host: So efficiency is only the first step. We still need to judge whether the result is useful.')] },
    { title: text('先把问题说清楚', 'Clarify the question first'), duration: 2840, days: 9, transcript: [text('主持人：什么样的问题，可以让一次讨论真正向前走？', 'Host: What kind of question helps a discussion move forward?'), text('嘉宾：明确目标、条件和评价方式。没有共同的标准，很容易各说各话。', 'Guest: Agree on the goal, conditions and evaluation criteria. Without shared standards, people talk past each other.'), text('主持人：把这些条件留下来，下一次才能知道发生了什么变化。', 'Host: Keep those conditions so you can see what has changed next time.')] },
  ] },
  { name: text('Future Signals', 'Future Signals'), type: 'YouTube', cover: 'cover-signals.svg', unread: true, episodes: [
    { title: text('模型之外，还有什么？', 'What lies beyond the model?'), duration: 4280, days: 1, transcript: [text('主持人：除了模型能力，还有哪些因素会影响我们使用 AI？', 'Host: Beyond model capabilities, what shapes how we use AI?'), text('嘉宾：工具所在的流程、协作者的反馈，以及一个具体任务的约束，都值得观察。', 'Guest: Look at the workflow, feedback from collaborators and the constraints of a specific task.'), text('主持人：同一个工具，放在不同环境里，效果也会不同。', 'Host: The same tool can have different effects in different settings.')] },
    { title: text('从原型到日常工具', 'From prototype to everyday tool'), duration: 3200, days: 8, transcript: [text('主持人：一个原型什么时候才算进入了日常工作？', 'Host: When does a prototype become part of everyday work?'), text('嘉宾：当人们反复使用它，并且能从真实反馈中改进它的时候。', 'Guest: When people use it repeatedly and improve it through real feedback.'), text('主持人：所以还需要看它能不能融入已有习惯。', 'Host: We also need to see whether it fits existing habits.')] },
  ] },
  { name: text('方法观察室', 'Method Observatory'), type: 'bilibili', cover: 'cover-method.svg', unread: true, episodes: [
    { title: text('好问题的形状', 'The shape of a good question'), duration: 3100, days: 3, transcript: [text('主持人：怎样判断，我们提出的是一个好问题？', 'Host: How do we know we have asked a good question?'), text('嘉宾：先约定一个可以检验的目标，再把适用条件说清楚。', 'Guest: Agree on a testable goal and make the applicable conditions clear.'), text('主持人：把问题、尝试和依据一起记录，比只留下结论更有帮助。', 'Host: Keeping the question, attempt and evidence together is more useful than saving only the conclusion.')] },
    { title: text('不同观点，如何对话', 'A conversation across perspectives'), duration: 2540, days: 10, transcript: [text('主持人：为什么同一个问题，会得到不同的回答？', 'Host: Why do people give different answers to the same question?'), text('嘉宾：人们看到的条件不同，也可能在关注不同的目标。', 'Guest: They may see different conditions or care about different goals.'), text('主持人：先把这些条件摆出来，才能理解分歧从哪里来。', 'Host: Make those conditions visible to understand where the disagreement comes from.')] },
  ] },
];
const subscriptionMessages = {
  initial: text('示例地址仅用于演示；不会发送订阅请求。', 'Sample URLs only; no subscription request is sent.'),
  invalid: text('请使用 http 或 https 链接。', 'Use an HTTP or HTTPS URL.'),
  youtube: text('YouTube 请填写频道地址，例如 youtube.com/@channel。', 'For YouTube, use a channel URL such as youtube.com/@channel.'),
  bilibili: text('B 站请填写 UP 主主页，例如 space.bilibili.com/12345678。', 'For Bilibili, use a creator URL such as space.bilibili.com/12345678.'),
  rss: text('RSS 地址预览已加入演示库；正式订阅时会读取并校验 RSS。', 'RSS URL preview added to the demo; the actual app reads and validates the feed.'),
  added: text('来源已识别，预览已加入演示库。正式应用会在后台同步节目。', 'Source detected and preview added to the demo. The actual app syncs episodes in the background.'),
  duplicate: text('这个地址已在本页演示库中。', 'This URL is already in this demo library.'),
};
let language = 'zh', mode = 'core', period = 'week', shot = 'listening', quoteIndex = 0;
let perspective = 'listening', selectedFeed = 0, readingEpisode = 0, recentOnly = false;
let nowPlaying = { feed: podcasts[0], episode: podcasts[0].episodes[0] }, playing = false, playbackTimer, position = 0;
let subscriptionMessage = 'initial';
const positions = new Map();
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
function formatTime(seconds) {
  const hours = Math.floor(seconds / 3600), minutes = Math.floor(seconds % 3600 / 60), rest = seconds % 60;
  return (hours ? hours + ':' + String(minutes).padStart(2, '0') : minutes) + ':' + String(rest).padStart(2, '0');
}
function renderSubscriptionStatus() {
  $('#subscribe-status').textContent = localized(subscriptionMessages[subscriptionMessage]);
  $('#subscribe-status').classList.toggle('is-error', ['invalid', 'youtube', 'bilibili'].includes(subscriptionMessage));
}
function renderPlayer() {
  $('#player-title').textContent = localized(nowPlaying.episode.title);
  $('#player-feed').textContent = localized(nowPlaying.feed.name);
  $('#player-cover').src = './assets/' + nowPlaying.feed.cover;
  $('#player-toggle').textContent = playing ? 'Ⅱ' : '▶';
  $('#player-toggle').setAttribute('aria-pressed', String(playing));
  $('#player-toggle').setAttribute('aria-label', localized(playing ? text('暂停模拟播放', 'Pause simulated playback') : text('开始模拟播放', 'Start simulated playback')));
  $('#player-seek').max = nowPlaying.episode.duration;
  $('#player-seek').value = position;
  $('#player-time').textContent = formatTime(position);
  $('#player-duration').textContent = formatTime(nowPlaying.episode.duration);
}
function setPlayback(next) {
  playing = next;
  clearInterval(playbackTimer);
  if (playing) playbackTimer = setInterval(() => {
    seekTo(position + 1);
    if (position === nowPlaying.episode.duration) setPlayback(false);
  }, 1000);
  renderPlayer();
}
function seekTo(next) {
  position = Math.max(0, Math.min(nowPlaying.episode.duration, next));
  positions.set(nowPlaying.episode, position);
  renderPlayer();
}
function renderListening() {
  const feed = podcasts[selectedFeed];
  const feedList = $('#listening-feeds');
  feedList.replaceChildren();
  podcasts.forEach((source, index) => {
    const button = makeElement('button', 'listening-feed');
    button.type = 'button';
    button.dataset.feed = index;
    button.setAttribute('aria-pressed', String(index === selectedFeed));
    const cover = makeElement('img', ''); cover.src = './assets/' + source.cover; cover.alt = '';
    button.append(cover, makeElement('span', '', localized(source.name)));
    if (source.unread) {
      const dot = makeElement('i', 'unread-dot'); dot.setAttribute('aria-hidden', 'true'); button.append(dot);
      button.setAttribute('aria-label', localized(source.name) + localized(text('，有未查看的更新', ', has unseen updates')));
    }
    button.addEventListener('click', () => {
      selectedFeed = index; readingEpisode = 0; source.unread = false;
      renderListening(); $('[data-feed="' + index + '"]').focus();
    });
    feedList.append(button);
  });
  $('#subscription-count').textContent = podcasts.length;
  $('#listening-title').textContent = localized(feed.name);
  $('#listening-feed-label').textContent = feed.type + ' / ' + localized(recentOnly ? text('最近 7 天', 'LAST 7 DAYS') : text('全部节目', 'ALL EPISODES'));
  $('#recent-toggle').setAttribute('aria-pressed', String(recentOnly));
  const episodeList = $('#listening-episodes'); episodeList.replaceChildren();
  feed.episodes.forEach((episode, index) => {
    if (recentOnly && episode.days > 7) return;
    const button = makeElement('button', 'listening-episode');
    button.type = 'button'; button.dataset.episode = index;
    button.setAttribute('aria-pressed', String(nowPlaying.episode === episode));
    const cover = makeElement('img', ''); cover.src = './assets/' + feed.cover; cover.alt = '';
    const copy = makeElement('span', '');
    copy.append(makeElement('strong', '', localized(episode.title)), makeElement('small', '', formatTime(episode.duration) + ' · ' + episode.days + localized(text(' 天前 · 点开收听', ' days ago · open to listen'))));
    button.append(cover, copy);
    button.addEventListener('click', () => {
      readingEpisode = index; setPlayback(false);
      nowPlaying = { feed, episode }; position = positions.get(episode) || 0;
      renderListening(); renderPlayer();
      $('[data-episode="' + index + '"]').focus();
    });
    episodeList.append(button);
  });
  const transcript = $('#listening-transcript'); transcript.replaceChildren();
  feed.episodes[readingEpisode].transcript.forEach((line, index) => {
    const row = makeElement('div', 'transcript-line');
    row.append(makeElement('span', '', formatTime(index * 52)), makeElement('p', '', localized(line)));
    transcript.append(row);
  });
}
function activatePerspective(next) {
  perspective = next;
  if (perspective !== 'listening') setPlayback(false);
  document.querySelectorAll('[data-view]').forEach(button => {
    const active = button.dataset.view === perspective;
    button.setAttribute('aria-selected', String(active)); button.tabIndex = active ? 0 : -1;
  });
  $('#listening-panel').hidden = perspective !== 'listening';
  $('#ai-panel').hidden = perspective !== 'ai';
}
function previewSubscription(event) {
  event.preventDefault();
  let url;
  try { url = new URL($('#subscribe-url').value.trim()); }
  catch { subscriptionMessage = 'invalid'; renderSubscriptionStatus(); return; }
  if (!['http:', 'https:'].includes(url.protocol)) { subscriptionMessage = 'invalid'; renderSubscriptionStatus(); return; }
  let type = 'RSS', template = 0;
  const hostname = url.hostname.toLowerCase();
  if (hostname === 'youtube.com' || hostname.endsWith('.youtube.com') || hostname === 'youtu.be') {
    if (hostname === 'youtu.be' || !/^\/(?:@[^/]+|(?:channel|c|user)\/[^/]+)(?:\/(?:videos|shorts|streams|featured))?\/?$/.test(url.pathname)) { subscriptionMessage = 'youtube'; renderSubscriptionStatus(); return; }
    type = 'YouTube'; template = 1;
  } else if (hostname === 'bilibili.com' || hostname.endsWith('.bilibili.com')) {
    if (hostname !== 'space.bilibili.com' || !/^\/\d+\/?$/.test(url.pathname)) { subscriptionMessage = 'bilibili'; renderSubscriptionStatus(); return; }
    type = 'bilibili'; template = 2;
  }
  const existing = podcasts.findIndex(feed => feed.url === url.href);
  if (existing >= 0) { selectedFeed = existing; subscriptionMessage = 'duplicate'; }
  else {
    const sample = podcasts[template];
    podcasts.push({ ...sample, name: text(type + ' 示例订阅', type + ' sample subscription'), url: url.href, unread: false, episodes: sample.episodes.map(episode => ({ ...episode })) });
    selectedFeed = podcasts.length - 1;
    subscriptionMessage = type === 'RSS' ? 'rss' : 'added';
  }
  readingEpisode = 0;
  renderListening(); renderSubscriptionStatus();
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
  renderCards(); renderPeriod(); renderShot(); renderQuote(); renderListening(); renderPlayer(); renderSubscriptionStatus();
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
const perspectiveButtons = [...document.querySelectorAll('[data-view]')];
perspectiveButtons.forEach(button => button.addEventListener('click', () => activatePerspective(button.dataset.view)));
$('.perspective-tabs').addEventListener('keydown', event => tabKeyboard(event, perspectiveButtons, button => activatePerspective(button.dataset.view)));
document.querySelectorAll('[data-open-view]').forEach(link => link.addEventListener('click', () => {
  activatePerspective(link.dataset.openView);
  if (link.tagName === 'BUTTON') $('#view-' + link.dataset.openView).focus();
}));
$('#subscribe-form').addEventListener('submit', previewSubscription);
document.querySelectorAll('[data-subscribe-example]').forEach(button => button.addEventListener('click', () => {
  $('#subscribe-url').value = exampleUrls[button.dataset.subscribeExample];
  $('#subscribe-url').focus();
}));
$('#recent-toggle').addEventListener('click', () => { recentOnly = !recentOnly; readingEpisode = 0; renderListening(); });
$('#player-toggle').addEventListener('click', () => { if (position === nowPlaying.episode.duration) seekTo(0); setPlayback(!playing); });
$('#player-back').addEventListener('click', () => seekTo(position - 15));
$('#player-forward').addEventListener('click', () => seekTo(position + 30));
$('#player-seek').addEventListener('input', event => seekTo(Number(event.target.value)));
document.addEventListener('visibilitychange', () => { if (document.hidden) setPlayback(false); });
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
renderCards(); renderPeriod(); renderShot(); renderQuote(); renderListening(); renderPlayer(); renderSubscriptionStatus();
document.documentElement.classList.add('js');
const reveals = new IntersectionObserver(entries => entries.forEach(entry => {
  if (entry.isIntersecting) { entry.target.classList.add('is-visible'); reveals.unobserve(entry.target); }
}), { threshold: .08 });
document.querySelectorAll('.reveal').forEach(element => reveals.observe(element));
