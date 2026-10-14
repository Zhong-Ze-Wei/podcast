export function evidenceSwipeStep(deltaX, deltaY) {
  if (Math.abs(deltaX) < 60 || Math.abs(deltaX) <= Math.abs(deltaY) * 1.3) return 0;
  return deltaX < 0 ? 1 : -1;
}

export function evidenceIndex(index, step, count) {
  return Math.max(0, Math.min(count - 1, index + step));
}

export function evidenceFor(item) {
  const primary = item.evidence?.length ? item.evidence
    : item.quote && typeof item.quote === 'object' ? [item.quote]
      : item.quote ? [item] : [];
  const seen = new Set();
  return primary.flatMap(quote => [quote, ...(quote.supporting_references || [])]).filter(quote => {
    const key = quoteKey(quote);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

const quoteKey = quote => `${quote.source_id || quote.episode_id}:${quote.quote}`;

export function evidenceGallery(selection, items) {
  const quotes = [];
  const seen = new Set();
  for (const item of items) {
    for (const quote of evidenceFor(item)) {
      const key = quoteKey(quote);
      if (!seen.has(key)) {
        seen.add(key);
        quotes.push({ ...quote, context_title: item.title || item.brief || selection.title });
      }
    }
  }
  for (const quote of selection.quotes) {
    if (!seen.has(quoteKey(quote))) {
      seen.add(quoteKey(quote));
      quotes.push({ ...quote, context_title: selection.title });
    }
  }
  const initialIndex = quotes.findIndex(quote => quoteKey(quote) === quoteKey(selection.quotes[0]));
  return { ...selection, quotes, initialIndex: Math.max(0, initialIndex) };
}
