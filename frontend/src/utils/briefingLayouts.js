export function getBriefingLayouts(t) {
  return [
  { id: 'space', name: t("ui.spacious"), description: t("ui.focusOnOneIdeaWithRoomTo") },
  { id: 'large', name: t("ui.largeType"), description: t("ui.readQuotationsOneSentenceAtATime") },
  { id: 'list', name: t("ui.list"), description: t("ui.scanQuicklyAndChooseWhatToListen") },
  { id: 'columns', name: t("ui.twoColumns"), description: t("ui.readViewpointsSideBySide") },
  { id: 'paper', name: t("ui.paper2"), description: t("ui.aReadingPageYouCanTakeWith") },
  { id: 'newspaper', name: t("ui.newspaper"), description: t("ui.warmWhiteColumnsLikeReadingANewspaper") },
  { id: 'notes', name: t("ui.notes"), description: t("ui.lightNotesWithOneIdeaPerCard") },
];
}
