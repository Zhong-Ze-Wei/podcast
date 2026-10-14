export function uiLocale(language) {
  return language?.startsWith('en') ? 'en-US' : 'zh-CN';
}

export function localizedLabel(item, language) {
  return uiLocale(language) === 'en-US' ? item.label || item.label_zh : item.label_zh || item.label;
}

export function templateDisplayName(template, t) {
  const builtIn = template.is_system && ['investment', 'tech', 'startup', 'learning', 'interview'].includes(template.name);
  return builtIn ? t(`ui.templateNames.${template.name}`) : template.display_name;
}

export function formatUiDate(value, language, options = {}) {
  if (!value) return '';
  return new Intl.DateTimeFormat(uiLocale(language), { timeZone: 'Asia/Hong_Kong', ...options }).format(new Date(value));
}

export function formatPeriodLabel(period, language) {
  if (!period?.start) return period?.label || '';
  const english = uiLocale(language) === 'en-US';
  const start = new Date(`${period.start}T00:00:00Z`);
  if (period.type === 'month') {
    return english
      ? `${new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(start)} · Monthly report`
      : `${period.start.slice(0, 4)}年${period.start.slice(5, 7)}月 月报`;
  }
  const end = new Date(start.getTime() + 6 * 86400000).toISOString().slice(0, 10);
  return `${period.start.replaceAll('-', '.')} — ${end.slice(0, 4) === period.start.slice(0, 4) ? end.slice(5).replace('-', '.') : end.replaceAll('-', '.')} ${english ? 'Weekly report' : '周报'}`;
}

const progressPatterns = [
  [/^收集材料：找到(\d+)期，已有正文(\d+)期$/, 'collect', ['total', 'ready']],
  [/^标题判定 (\d+)\/(\d+)，不确定的节目保留$/, 'screen', ['done', 'total']],
  [/^逐篇分析 (\d+)\/(\d+) · 复用(\d+)期 · 正在分析《(.+)》$/, 'analyze', ['done', 'total', 'reused', 'title']],
  [/^逐篇分析 (\d+)\/(\d+) · 复用(\d+)期 · 新分析(\d+)期 · 失败(\d+)期$/, 'analyzed', ['done', 'total', 'reused', 'new', 'failed']],
  [/^观点分析 (\d+)\/(\d+) 段 · 已复用 (\d+) 段$/, 'claims', ['done', 'total', 'reused']],
];

const feedProgressPatterns = [
  [/^视频列表已更新：新增 (\d+) 期$/, 'videos', ['count']],
  [/^后台获取文稿 (\d+)\/(\d+)$/, 'transcripts', ['done', 'total']],
  [/^文稿已更新：(\d+) 期，暂不可用 (\d+) 期$/, 'transcriptsDone', ['count', 'failed']],
];

const messageCatalogs = new WeakMap();

function messageCatalog(t) {
  if (!messageCatalogs.has(t)) {
    const messages = new Map();
    const remember = (catalog, prefix) => {
      for (const [key, value] of Object.entries(catalog)) {
        if (typeof value === 'object') remember(value, `${prefix}${key}.`);
        else if (!value.includes('{{')) messages.set(value, `${prefix}${key}`);
      }
    };
    for (const lng of ['zh', 'en']) {
      remember(t('common', { lng, returnObjects: true }), 'common.');
      remember(t('ui', { lng, returnObjects: true }), 'ui.');
      remember(t('feedDetail', { lng, returnObjects: true }), 'feedDetail.');
    }
    messageCatalogs.set(t, messages);
  }
  return messageCatalogs.get(t);
}

// Translate known product messages at display time so saved task history and open
// notices follow the language switch. Episode titles and provider errors stay intact.
export function localizeUiMessage(message, t) {
  if (!message) return message;
  const messages = messageCatalog(t);
  if (messages.has(message)) return t(messages.get(message));
  for (const [pattern, key, fields] of feedProgressPatterns) {
    const match = message.match(pattern);
    if (match) return t(`tasks.progress.${key}`, Object.fromEntries(fields.map((field, index) => [field, match[index + 1]])));
  }
  for (const [pattern, key, fields] of progressPatterns) {
    const match = message.match(pattern);
    if (match) return t(`ui.progress.${key}`, Object.fromEntries(fields.map((field, index) => [field, match[index + 1]])));
  }
  const section = message.match(/^已(整理|生成)(核心提要|原话精选|共性与分歧|新词与方法|提到的资料)$/);
  if (section) {
    return t(`ui.progress.${section[1] === '整理' ? 'sectionSaved' : 'sectionGenerated'}`, { section: t(messages.get(section[2])) });
  }
  return message;
}
