import { useTranslation } from 'react-i18next';
import React from 'react';
import { ChevronDown, ExternalLink } from 'lucide-react';
import { evidenceFor, evidenceGallery } from '../../utils/evidenceNavigation';
import './episode-analysis.css';

const usableUrl = url => typeof url === 'string' && /^https?:\/\//i.test(url);

// Both the traditional episode page and briefing page read this same saved analysis.
export default function EpisodeAnalysisContent({ reading, onEvidence, onSource }) {
  const { t } = useTranslation();
  const RESOURCE_LABELS = { book: t("ui.book"), article: t("ui.article"), paper: t("ui.paper"), tool: t("ui.tool"), website: t("ui.website"), report: t("ui.report"), podcast: t("ui.podcast") };
  const points = reading.points || [];
  const concepts = reading.concepts || [];
  const quotes = reading.quotes || [];
  const resources = reading.resources || [];
  const evidenceButton = (item, label = t("ui.sourceEvidence")) => {
    const evidence = evidenceFor(item);
    return evidence.length > 0 && onEvidence && <button className="episode-analysis-link" onClick={() => onEvidence(evidenceGallery({ title: item.title || item.brief || t("ui.originalQuotation"), quotes: evidence }, [...points, ...concepts, ...quotes, ...resources]))}>{label}<ExternalLink size={13} /></button>;
  };

  return <div className="episode-analysis-content">
    {reading.rejected_items?.length > 0 && <p className="episode-analysis-boundary" role="status">{t("ui.thereAre")} {reading.rejected_items.length} {t("ui.itemsWithoutConfirmedSourceEvidenceTheyWere")}</p>}
    {reading.excluded_quote_count > 0 && <p className="episode-analysis-boundary" role="status">{t("ui.additionalSpeakerMetadataExcluded")} {reading.excluded_quote_count} {t("ui.quotationsSpanningMultipleSpeakersTheRemainingAnalysis")}</p>}
    <section className="episode-analysis-summary"><span className="episode-analysis-label">{t("ui.overviewAIAnalysis")}</span><p>{reading.takeaway}</p></section>
    {points.length > 0 && <section aria-label={t("ui.keyTopics")}><h3 className="episode-analysis-section-title">{t("ui.keyTopics")}</h3><div className="episode-analysis-points">{points.map((point, index) => <section key={point.id || index}><div className="episode-analysis-point-heading"><h4>{point.title}</h4>{evidenceButton(point)}</div><p>{point.meaning || point.text}</p>{point.boundary && <p className="episode-analysis-boundary">{t("ui.conditions")}{point.boundary}</p>}</section>)}</div></section>}
    {concepts.length > 0 && <section aria-label={t("ui.conceptsMethods")}><h3 className="episode-analysis-section-title">{t("ui.conceptsMethods")}</h3><div className="episode-analysis-concepts">{concepts.map((concept, index) => <section key={concept.id || index}><h4>{concept.title || concept.name}</h4><p>{concept.meaning || concept.text || concept.definition}</p>{evidenceButton(concept)}</section>)}</div></section>}
    {quotes.length > 0 && <details className="episode-analysis-details"><summary>{t("ui.keyQuotations")} <span>{quotes.length} {t("ui.passages")}</span><ChevronDown size={16} /></summary><div>{quotes.map((quote, index) => <section key={quote.id || index}>{quote.brief && <h4>{quote.brief}</h4>}<blockquote>{quote.translation || quote.quote}</blockquote>{quote.speaker && <p className="episode-analysis-label">{quote.speaker}</p>}{evidenceButton(quote, quote.translation ? t("ui.originalSource") : t("ui.viewSource"))}</section>)}</div></details>}
    {resources.length > 0 && <details className="episode-analysis-details"><summary>{t("ui.mentionedResources")} <span>{resources.length} {t("ui.resources")}</span><ChevronDown size={16} /></summary><div>{resources.map((resource, index) => <section key={resource.id || index}><span className="episode-analysis-label">{RESOURCE_LABELS[resource.resource_kind] || t("ui.resource")} · {['recommended', 'explicit_recommendation'].includes(resource.relation) ? t("ui.guestRecommendation") : t("ui.mentionedInTheEpisode")}</span><h4>{resource.title}</h4>{resource.text && <p>{resource.text}</p>}<div className="episode-analysis-actions">{usableUrl(resource.url) && <a className="episode-analysis-link" href={resource.url} target="_blank" rel="noopener noreferrer">{t("ui.openResource")}<ExternalLink size={13} /></a>}{evidenceButton(resource, t("ui.supportingQuotation"))}{!evidenceFor(resource).length && resource.source_id && onSource && <button className="episode-analysis-link" onClick={() => onSource(resource)}>{t("ui.viewTranscript")}</button>}</div></section>)}</div></details>}
  </div>;
}
