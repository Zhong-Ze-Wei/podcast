// 只删除服务器确认导入的旧 ID；未解析和失败的数据仍留在原用户的浏览器记录中。
export async function importBrowserFavorites(storage, key, importIds) {
  const ids = JSON.parse(storage.getItem(key) || '[]');
  const imported = new Set();
  const unresolved = new Set();
  for (let offset = 0; offset < ids.length; offset += 500) {
    const result = (await importIds(ids.slice(offset, offset + 500))).data;
    result.imported.forEach(id => imported.add(id));
    result.unresolved.forEach(id => unresolved.add(id));
  }
  const latest = JSON.parse(storage.getItem(key) || '[]');
  storage.setItem(key, JSON.stringify(latest.filter(id => !imported.has(id))));
  return { imported: [...imported], unresolved: [...unresolved] };
}

export async function loadReportFavoriteIds(report, list) {
  const ids = [];
  let page = 1;
  let hasNext = true;
  while (hasNext) {
    const response = await list({ period_type: report.period.type, period_start: report.period.start, mode: report.mode, page, per_page: 100 });
    ids.push(...response.data.map(favorite => favorite.item_id));
    hasNext = response.pagination.has_next;
    page += 1;
  }
  return ids;
}
