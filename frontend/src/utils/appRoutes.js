export function parseAppPath(pathname) {
  const parts = pathname.split('/').filter(Boolean);
  if (parts[0] === 'episodes' && parts[1]) {
    return { type: 'episode', id: parts[1] };
  }
  if (parts[0] === 'feeds' && parts[1]) {
    return { type: 'feed', id: parts[1] };
  }
  if (parts[0] === 'episodes') return { type: 'view', view: 'list' };
  if (parts[0] === 'favorites') return { type: 'view', view: 'favorites' };
  if (parts[0] === 'settings') return { type: 'view', view: 'settings' };
  if ((parts[0] === 'briefing' || parts[0] === 'briefing-lab') && parts[1] === 'settings') return { type: 'view', view: 'settings', section: 'briefing', mode: 'ai-briefing' };
  if (parts[0] === 'briefing' || parts[0] === 'briefing-lab') return { type: 'view', view: parts[1] === 'settings' ? 'briefingSettings' : parts[1] === 'saved' ? 'briefingSaved' : 'briefing' };
  return { type: 'view', view: 'workspace' };
}
