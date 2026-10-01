export function shouldAutoOpenTaskPanel({ mobile, activeCount, previousActiveCount, userClosed }) {
  return !mobile && activeCount > 0 && previousActiveCount === 0 && !userClosed;
}
