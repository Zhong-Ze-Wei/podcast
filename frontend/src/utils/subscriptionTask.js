export function readableSubscriptionUrl(value) {
  try {
    return decodeURI(value);
  } catch (error) {
    if (error instanceof URIError) return value;
    throw error;
  }
}

export function subscriptionProgress(message, t) {
  const stages = {
    '正在识别订阅来源': 'subscriptionResolving',
    '订阅已保存，正在获取频道封面': 'subscriptionSaved',
    '订阅已添加，正在后台更新节目': 'subscriptionDone',
  };
  return stages[message] ? t(`tasks.progress.${stages[message]}`) : message;
}
