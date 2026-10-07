const patterns = [
  [/^视频列表已更新：新增 (\d+) 期$/, 'videos', ['count']],
  [/^后台获取文稿 (\d+)\/(\d+)$/, 'transcripts', ['done', 'total']],
  [/^文稿已更新：(\d+) 期，暂不可用 (\d+) 期$/, 'transcriptsDone', ['count', 'failed']],
  [/^后台补齐节目资料 (\d+)\/(\d+)$/, 'episodeDetails', ['done', 'total']],
  [/^节目资料更新完成；新增文稿 (\d+) 期，暂不可用 (\d+) 期$/, 'episodeDetailsDone', ['count', 'failed']],
];
export function localizeFeedProgress(message, t) {
  for (const [pattern, key, fields] of patterns) {
    const match = message.match(pattern);
    if (match) return t(`tasks.progress.${key}`, Object.fromEntries(fields.map((field, index) => [field, match[index + 1]])));
  }
  return message;
}
