"""固定 A4 版式：浏览器测量后精选，HTML 预览与 PDF 使用同一份分页内容。"""
import base64
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


VARIANT_NAMES = {
    "overview": "本期速览", "episodes": "逐期摘录", "concepts": "本期新词",
    "quotes": "金句摘录", "resources": "提到的资料",
}
KIND_NAMES = {
    "concept": "本期术语", "quote": "原话摘录", "resource": "提到的资料",
    "background": "补充背景", "episode": "节目摘录",
    "insight": "核心提要 · AI 归纳", "connection": "跨节目比较 · AI 归纳",
}
RELATION_NAMES = {"mentioned": "节目提到", "recommended": "嘉宾明确推荐", "external": "补充背景"}
RESOURCE_NAMES = {"book": "书", "article": "文章", "paper": "论文", "tool": "工具", "website": "网站", "other": "资料"}
CSS = """
@page { size: A4; margin: 12mm; }
* { box-sizing: border-box; }
html { background: #e9e8ec; }
body { margin: 0; color: #202027; font-family: 'Microsoft YaHei', 'Noto Sans CJK SC', 'SimHei', sans-serif;
 font-size: 10pt; line-height: 1.52; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
a { color: #6240a1; text-decoration: none; overflow-wrap: anywhere; }
.report-page { width: 186mm; height: 273mm; padding: 0; margin: 12mm auto; background: white;
 display: flex; flex-direction: column; break-after: page; }
.report-page:last-of-type { break-after: auto; }
.report-header { flex: none; padding-bottom: 5mm; border-bottom: .5mm solid #7450ac; margin-bottom: 4mm; }
.brand { color: #71519a; font-size: 8.5pt; letter-spacing: .05em; margin-bottom: 2mm; }
h1 { font-size: 18pt; line-height: 1.25; margin: 0 0 2mm; font-weight: 700; }
.report-meta { font-size: 8.5pt; color: #64606c; }
.columns { display: flex; gap: 6mm; flex: 1; min-height: 0; align-items: flex-start; }
.column { width: 90mm; flex: none; }
.card { padding: 3.1mm 3.4mm; margin: 0 0 3mm; border: .25mm solid #e1dce9;
 border-radius: 1.3mm; break-inside: avoid; background: #fff; overflow-wrap: anywhere; }
.card-kind { font-size: 8pt; color: #7653a5; margin-bottom: 1mm; font-weight: 700; }
h2 { font-size: 11.5pt; line-height: 1.35; margin: 0 0 1.5mm; }
p { margin: 0 0 1.8mm; }
blockquote { margin: 2mm 0; padding: 1.8mm 0 1.8mm 2.6mm; border-left: .65mm solid #a88ac8;
 line-height: 1.5; font-size: 10.5pt; color: #282132; }
.quote-card blockquote { font-weight: 500; }
.label { color: #65606d; font-size: 8.5pt; }
.source { border-top: .2mm solid #eeebf2; padding-top: 1.9mm; margin-top: 2mm;
 color: #66616e; font-size: 8.5pt; line-height: 1.42; }
.source .feed { color: #443d4f; font-weight: 600; }
.source a { display: inline-block; margin-top: 1mm; margin-right: 2.5mm; }
.child { border-top: .2mm solid #eeebf2; margin-top: 2.2mm; padding-top: 2mm; }
.child h3 { margin: 0 0 1mm; font-size: 9.5pt; }
.child .card { border: 0; padding: 0; margin: 0; }
.child p, .child blockquote { font-size: 10pt; }
.child .source { border: 0; padding-top: 0; margin-top: 1mm; font-size: 8.5pt; }
.episode-piece { border-top: .2mm solid #eeebf2; margin-top: 2mm; padding-top: 1.7mm; }
.episode-piece h3 { margin: 0 0 1mm; font-size: 10.5pt; line-height: 1.35; }
.piece-meta { font-size: 8.5pt; color: #7653a5; margin-bottom: 1mm; }
.episode-piece blockquote { font-size: 10pt; margin: 1mm 0 1.5mm; padding-top: 1mm; padding-bottom: 1mm; }
.report-footer { flex: none; min-height: 8mm; padding-top: 2.3mm; margin-top: 2mm;
 border-top: .2mm solid #e2deea; font-size: 8pt; line-height: 1.45; color: #77717f; }
.footer-row { display: flex; justify-content: space-between; gap: 4mm; }
.source-index { flex: none; margin-top: 3mm; padding-top: 2.5mm; border-top: .3mm solid #dcd5e7; }
.source-index h2 { font-size: 10pt; margin-bottom: 1.7mm; }
.index-grid { display: grid; grid-template-columns: 1fr 1fr; column-gap: 6mm; row-gap: 1.5mm; }
.index-item { font-size: 8pt; line-height: 1.4; overflow-wrap: anywhere; }
.index-item strong { font-weight: 600; color: #51465e; }
.empty { padding: 8mm 3mm; color: #766f80; font-size: 10pt; }
.measure-stack { width: 90mm; position: absolute; left: -10000px; top: 0; }
@media print { html { background: white; } .report-page { margin: 0; } }
"""

READING_CSS = """
body.reading-edition { font-size: 11pt; }
.reading-edition .card { border: 0; border-bottom: .25mm solid #e2deea; border-radius: 0; padding: 4mm 0; margin-bottom: 4mm; }
.reading-edition .card-kind { display: none; }
.reading-edition blockquote { border: 0; padding: 0; font-size: 14pt; line-height: 1.65; margin: 2mm 0 4mm; }
.reading-edition .source { border: 0; font-size: 9.5pt; }
.reading-edition .label { font-size: 9.5pt; }
.reading-edition .original-quote blockquote { font-size: 11pt; line-height: 1.6; }
.reading-edition .report-thread { margin: 0 0 4mm; font-size: 11pt; }
.reading-edition .report-thread .label { display: block; margin-bottom: 1mm; }
.reading-edition .source-index { margin: 0 0 5mm; }
"""


def _escape(value):
    return html.escape(str(value or ""), quote=True)


def _safe_url(value):
    value = str(value or "")
    parsed = urlsplit(value)
    return value if parsed.scheme in ("http", "https") and parsed.netloc else ""


def _anchor(label, url):
    return f'<a href="{_escape(url)}" target="_blank" rel="noopener noreferrer">{_escape(label)}</a>'


def _time_label(value):
    if value is None:
        return ""
    seconds = max(0, int(float(value)))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def _local_link(item, base_url):
    if not item.get("episode_id") or not _safe_url(base_url):
        return ""
    query = {}
    if item.get("start") is not None:
        query["t"] = max(0, int(float(item["start"])))
    return f"{base_url.rstrip('/')}/episodes/{item['episode_id']}" + (f"?{urlencode(query)}" if query else "")


def _public_link(item):
    url = _safe_url(item.get("url"))
    if not url or item.get("start") is None:
        return url
    parsed = urlsplit(url)
    if parsed.hostname in ("www.youtube.com", "youtube.com", "youtu.be"):
        query = dict(parse_qsl(parsed.query))
        query["t"] = str(max(0, int(float(item["start"]))))
        return urlunsplit(parsed._replace(query=urlencode(query)))
    return url


def _source_html(item, sources, base_url, compact=False):
    source = sources.get(item.get("source_id"), {})
    feed = item.get("feed") or source.get("feed") or ""
    title = item.get("source_title") or source.get("title") or ""
    speaker = item.get("speaker")
    timing = _time_label(item.get("start"))
    if timing and item.get("end") is not None and item["end"] > item["start"]:
        timing += " - " + _time_label(item["end"])
    parts = [] if compact else [f'<span class="feed">{_escape(feed)}</span>']
    duration = source.get("duration")
    if not compact and isinstance(duration, (int, float)) and 0 < duration <= 120:
        parts.append("短片")
    if not compact and item.get("kind") != "episode":
        parts.append(_escape(title))
    parts.extend(_escape(value) for value in (speaker, timing) if value)
    local = _local_link({**source, **item}, base_url)
    public = _public_link({**source, **item, "url": item.get("url") or source.get("url")})
    links = []
    if local:
        label = "回听此处" if timing else "打开节目"
        links.append(_anchor(label, local))
    if public:
        label = "公开资料" if item.get("kind") in ("resource", "background") and _safe_url(item.get("url")) else "公开节目"
        links.append(_anchor(label, public))
    return '<div class="source">' + " · ".join(p for p in parts if p) + "<br>" + "".join(links) + "</div>"


def _card_html(item, sources, base_url, compact=False):
    kind = item.get("kind", "concept")
    relation = KIND_NAMES.get(kind, "节目摘录")
    if kind in ("resource", "background"):
        relation = RELATION_NAMES.get(item.get("relation")) or item.get("relation") or relation
    if kind == "resource" and item.get("resource_kind") in RESOURCE_NAMES:
        relation = RESOURCE_NAMES[item["resource_kind"]] + " · " + relation
    if kind == "connection":
        relation = {"commonality": "共同点", "difference": "分歧", "complementary": "互补"}.get(item.get("relation"), "联系") + " · AI 比较"
    body = [f'<div class="card-kind">{_escape(relation)}</div>']
    if item.get("title"):
        body.append(f'<h2>{_escape(item["title"])}</h2>')
    if item.get("text") and not (kind == "episode" and item["text"].startswith("本期摘录：")):
        body.append(f'<p>{_escape(item["text"])}</p>')
    if kind == "quote":
        if item.get("original_quote"):
            body.append('<div class="label">英文原话 · 对照首页译文</div>')
        if item.get("translation"):
            body.append(f'<div class="label">译文 · 原句见节目文稿</div><blockquote>{_escape(item["translation"])}</blockquote>')
        elif item.get("quote"):
            body.append(f'<blockquote>{_escape(item["quote"])}</blockquote>')
    context = item.get("brief") or item.get("context")
    if context:
        body.append(f'<p><span class="label">当时在谈：</span>{_escape(context)}</p>')
    if kind == "background" and item.get("relation") == "external":
        details = [item.get("publisher", "")]
        if item.get("accessed_at"):
            details.append("查阅于 " + _date_label(item["accessed_at"]))
        body.append(f'<p class="label">{_escape(" · ".join(value for value in details if value))}</p>')
    for child in item.get("children", []):
        body.append(_episode_piece(child, sources, base_url))
    if item.get("topic_tags"):
        body.append(f'<p class="label">{_escape(" · ".join(item["topic_tags"]))}</p>')
    if kind == "connection":
        # 多来源比较必须把另一方的出处带进纸面，不能只印第一期。
        seen_sources = {item.get("source_id")}
        for evidence in item.get("evidence", []):
            if evidence["source_id"] not in seen_sources:
                body.append(_source_html(evidence, sources, base_url, compact=compact))
                seen_sources.add(evidence["source_id"])
    body.append(_source_html(item, sources, base_url, compact=compact))
    original_class = " original-quote" if item.get("original_quote") else ""
    return f'<article class="card {kind}-card{original_class}" data-card-id="{_escape(item.get("id"))}">' + "".join(body) + "</article>"


def _episode_piece(item, sources, base_url):
    """逐期纸面只保留术语解释、原话语境和资料说明，来源继承所属节目。"""
    kind = item["kind"]
    source = sources.get(item.get("source_id"), {})
    timing = _time_label(item.get("start"))
    local = _local_link({**source, **item}, base_url)
    if timing and local:
        timing = _anchor(timing, local)
    else:
        timing = _escape(timing)
    label = KIND_NAMES.get(kind, "节目摘录")
    meta = _escape(label) + (" · " + _escape(item["speaker"]) if item.get("speaker") else "")
    if timing:
        meta += " · " + timing
    body = [f'<div class="piece-meta">{meta}</div>', f'<h3>{_escape(item.get("title"))}</h3>']
    if kind == "quote":
        if item.get("translation"):
            body.append('<div class="label">译文 · 原句见节目文稿</div>')
            quote = item["translation"]
        else:
            quote = item.get("quote", "")
        body.append(f'<blockquote>{_escape(quote)}</blockquote>')
        if item.get("context"):
            body.append(f'<p><span class="label">当时在谈：</span>{_escape(item["context"])}</p>')
    elif item.get("text"):
        body.append(f'<p>{_escape(item["text"])}</p>')
    if kind == "resource" and _safe_url(item.get("url")):
        body.append(_anchor("打开资料", item["url"]))
    return '<div class="episode-piece">' + "".join(body) + '</div>'


def _date_label(value):
    if not value:
        return ""
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")


def _index_html(report, base_url):
    entries = []
    for source in report.get("sources", []):
        title = _escape(source.get("title"))
        link = _public_link(source) or _local_link(source, base_url)
        if link:
            title = _anchor(source.get("title"), link)
        duration = source.get("duration")
        short = " · 短片" if isinstance(duration, (int, float)) and 0 < duration <= 120 else ""
        entries.append(f'<div class="index-item"><strong>{_escape(source.get("feed"))}{short}</strong><br>{title}</div>')
    return '<section class="source-index"><h2>本次材料索引</h2><div class="index-grid">' + "".join(entries) + "</div></section>"


def _document(report, columns, selected, omitted, base_url, measurement_cards=None):
    source_map = {source.get("id"): source for source in report.get("sources", [])}
    reading_edition = report.get("reading_edition")
    name = report["title"] if report.get("mode_report") else "原话精选" if reading_edition else VARIANT_NAMES[report["variant"]]
    title = report.get("topic") or report.get("title") or name
    coverage = report.get("coverage", {})
    source_count = coverage.get("sources", len(source_map))
    date = _date_label(report.get("generated_at"))
    pages = []
    for page_index, page_columns in enumerate(columns):
        continuation = {
            "overview": "节目背景与资料索引", "episodes": "更多节目摘录与材料索引",
            "concepts": "更多术语与相关背景", "quotes": "更多原话与相关背景",
            "resources": "更多资料与嘉宾背景",
        }[report["variant"]]
        if reading_edition and report.get("mode_report") and report.get("mode") == "quotes":
            continuation = "更多原话与材料来源"
        elif reading_edition:
            continuation = "原话对照与材料来源"
        elif report.get("mode_report"):
            continuation = "更多内容与材料来源"
        heading = title if page_index == 0 else continuation
        meta = f"{name} · {source_count} 篇有文稿的节目 · {date}"
        header = f'<header class="report-header"><div class="brand">PodMaster · 播客简报</div><h1>{_escape(heading)}</h1><div class="report-meta">{_escape(meta)}</div></header>'
        body = '<div class="columns">' + "".join('<div class="column">' + "".join(_card_html(card, source_map, base_url) for card in column) + '</div>' for column in page_columns) + '</div>'
        index = _index_html(report, base_url) if page_index == 1 else ""
        threads = ""
        if reading_edition and page_index == 1:
            selected_quote_ids = {card["id"] for page in columns for column in page for card in column if not card.get("original_quote")}
            supported_threads = [thread for thread in report.get("threads", [])
                                 if measurement_cards is not None or all(item_id in selected_quote_ids for item_id in thread["supporting_item_ids"])]
            threads = "".join('<section class="report-thread"><span class="label">共同谈到 · AI 归纳</span><p>' + _escape(thread["text"]) + '</p></section>' for thread in supported_threads)
        unit = "句" if reading_edition else "块"
        status = f"精选 {selected} {unit} · 另有 {omitted} {unit}留在网页" if omitted else f"收录 {selected} {unit}"
        if reading_edition and page_index == 1:
            original_total = sum(bool(card.get("translation")) for page in columns for column in page for card in column)
            original_count = sum(bool(card.get("original_quote")) for column in page_columns for card in column)
            if original_count < original_total:
                status += f" · 英文原话对照 {original_count}/{original_total} 句，完整原话见文稿"
        full = _anchor("查看完整简报与原文", base_url.rstrip("/") + "/briefing") if _safe_url(base_url) else ""
        note = "原话来自保存的文稿；译文辅助阅读。回听时间以字幕或转录段落为准。" if reading_edition else "引文来自保存的文稿；时间精度以字幕或转录段落为准。联网补充标明来源。"
        if report.get("mode_report") and not reading_edition:
            note = "AI 提要与比较依据保存的全文记录。证据原话见网页或文稿；回听时间以转录段落为准。"
        footer = f'<footer class="report-footer"><div class="footer-row"><span>{status} · {full}</span><span>{page_index + 1} / {len(columns)}</span></div><div>{note}</div></footer>'
        content = threads + index + body if reading_edition and page_index == 1 else body + index
        pages.append(f'<section class="report-page" data-page="{page_index + 1}">{header}{content}{footer}</section>')
    measure = ""
    if measurement_cards is not None:
        measure = '<div class="measure-stack">' + "".join(_card_html(card, source_map, base_url) for card in measurement_cards) + '</div>'
    edition_class = ' class="reading-edition"' if report.get("reading_edition") else ""
    styles = CSS + (READING_CSS if report.get("reading_edition") else "")
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>{_escape(name)}</title><style>{styles}</style></head><body{edition_class} data-selected-count="{selected}" data-omitted-count="{omitted}">' + "".join(pages) + measure + "</body></html>"


def _chrome_path():
    configured = os.environ.get("BRIEFING_PDF_CHROME")
    candidates = [configured, shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser")]
    for directory in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
        if directory:
            candidates.append(str(Path(directory) / "Google/Chrome/Application/chrome.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("PDF 排版需要 Chrome；请安装 Chrome 或设置 BRIEFING_PDF_CHROME。")


class _PrintBrowser:
    """单次隔离的无窗口 Chrome；不访问用户 Chrome 配置或登录状态。"""
    def __enter__(self):
        from websockets.sync.client import connect

        self.profile = tempfile.TemporaryDirectory(prefix="podmaster-report-", ignore_cleanup_errors=True)
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.process = subprocess.Popen([
            _chrome_path(), "--headless=new", "--no-first-run", "--disable-extensions",
            "--disable-background-networking", "--disable-component-update", "--remote-debugging-port=0",
            f"--user-data-dir={self.profile.name}", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        active_port = Path(self.profile.name) / "DevToolsActivePort"
        try:
            port, path = _wait_debugger_address(active_port, self.process)
        except RuntimeError:
            self.close()
            raise
        self.socket = connect(f"ws://127.0.0.1:{port}{path}", max_size=32 * 1024 * 1024, open_timeout=10)
        self.sequence = 0
        target = self.command("Target.createTarget", {"url": "about:blank"})["targetId"]
        self.session_id = self.command("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
        self.command("Page.enable", session=True)
        self.command("Emulation.setEmulatedMedia", {"media": "print"}, session=True)
        return self

    def command(self, method, params=None, session=False):
        self.sequence += 1
        message = {"id": self.sequence, "method": method, "params": params or {}}
        if session:
            message["sessionId"] = self.session_id
        self.socket.send(json.dumps(message))
        while True:
            response = json.loads(self.socket.recv(timeout=30))
            if response.get("id") == self.sequence:
                if "error" in response:
                    raise RuntimeError(f"PDF 排版失败：{response['error']['message']}")
                return response.get("result", {})

    def set_html(self, content):
        frame = self.command("Page.getFrameTree", session=True)["frameTree"]["frame"]["id"]
        self.command("Page.setDocumentContent", {"frameId": frame, "html": content}, session=True)
        self.command("Runtime.evaluate", {"expression": "document.fonts.ready.then(() => true)", "awaitPromise": True}, session=True)

    def measure(self):
        expression = """(() => ({
          cards: [...document.querySelectorAll('.measure-stack > .card')].map(el => ({
            id: el.dataset.cardId, height: el.getBoundingClientRect().height + parseFloat(getComputedStyle(el).marginBottom)})),
          pages: [...document.querySelectorAll('.report-page')].map(el => ({
            available: el.querySelector('.columns').getBoundingClientRect().height,
            columns: [...el.querySelectorAll('.column')].map(c => c.getBoundingClientRect().height),
            overflow: el.scrollHeight > el.clientHeight + 1}))
        }))()"""
        result = self.command("Runtime.evaluate", {"expression": expression, "returnByValue": True}, session=True)
        return result["result"]["value"]

    def pdf(self):
        result = self.command("Page.printToPDF", {"printBackground": True, "preferCSSPageSize": True,
                              "displayHeaderFooter": False}, session=True)
        return base64.b64decode(result["data"])

    def close(self):
        if hasattr(self, "socket"):
            self.socket.send(json.dumps({"id": self.sequence + 1, "method": "Browser.close"}))
            self.socket.close()
        if hasattr(self, "process"):
            if not hasattr(self, "socket") and self.process.poll() is None:
                self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if hasattr(self, "profile"):
            shutil.rmtree(self.profile.name, ignore_errors=True)
            self.profile.cleanup()

    def __exit__(self, *_):
        self.close()


def _wait_debugger_address(active_port, process):
    """Windows 写入端口文件期间可能短暂独占；读到两行后才连接。"""
    deadline = time.monotonic() + 15
    while process.poll() is None and time.monotonic() < deadline:
        try:
            lines = active_port.read_text().splitlines()
        except OSError:
            lines = []
        if len(lines) >= 2 and lines[0] and lines[1]:
            return lines[:2]
        time.sleep(.05)
    raise RuntimeError("Chrome PDF 排版进程未能启动。")


def _candidates(report, pages):
    cards = [card for section in report.get("sections", []) for card in section.get("items", [])]
    if report.get("mode_report") and report.get("mode") != "quotes":
        return cards, cards
    kind_order = {
        "overview": ("concept", "quote", "resource", "episode", "background"),
        "episodes": ("episode", "background"), "concepts": ("concept", "background", "resource"),
        "quotes": ("quote", "background"), "resources": ("resource", "background"),
    }[report["variant"]]
    budgets = {
        "overview": {"concept": 6 if pages == 2 else 3, "quote": 6 if pages == 2 else 3,
                     "resource": 4 if pages == 2 else 2, "episode": 1, "background": 2 if pages == 2 else 0},
        "episodes": {"episode": 10 if pages == 2 else 4, "background": 2 if pages == 2 else 0},
        "concepts": {"concept": 10 if pages == 2 else 6, "background": 2 if pages == 2 else 0, "resource": 2 if pages == 2 else 0},
        "quotes": {"quote": 10 if pages == 2 else 6, "background": 2 if pages == 2 else 0},
        "resources": {"resource": 8 if pages == 2 else 5, "background": 2 if pages == 2 else 0},
    }[report["variant"]]
    chosen = []
    for kind in kind_order:
        matching = [card for card in cards if card.get("kind") == kind]
        if kind == "background":
            matching.sort(key=lambda card: card.get("relation") != "external")
        chosen.extend(matching[:budgets[kind]])
    if report["variant"] == "overview":
        buckets = {kind: [card for card in chosen if card["kind"] == kind] for kind in kind_order}
        chosen = []
        while any(buckets.values()):
            for kind in kind_order:
                if buckets[kind]:
                    chosen.append(buckets[kind].pop(0))
    if pages == 2 and report["variant"] != "episodes":
        first_background = next((card for card in chosen if card.get("kind") == "background"), None)
        if first_background is not None:
            chosen.remove(first_background)
            chosen.insert(0, first_background)
    if report.get("reading_edition") and pages == 2:
        originals = [{**card, "id": "original-" + card["id"], "original_quote": True,
                      "original_item_id": card["id"], "translation": "", "title": "", "brief": "", "context": ""}
                     for card in chosen if card.get("translation")]
        chosen.extend(originals)
    return cards, chosen


@lru_cache(maxsize=24)
def _prepare(serialized, pages, base_url):
    report = json.loads(serialized)
    all_cards, candidates = _candidates(report, pages)
    empty_columns = [[[], []] for _ in range(pages)]
    measurement = _document(report, empty_columns, 0, len(all_cards), base_url, candidates)
    with _PrintBrowser() as browser:
        browser.set_html(measurement)
        metrics = browser.measure()
        height_map = {card["id"]: card["height"] for card in metrics["cards"]}
        capacities = [page["available"] - 3 for page in metrics["pages"]]
        columns = [[[], []] for _ in range(pages)]
        used = [[0, 0] for _ in range(pages)]
        selected_ids = set()
        for card in candidates:
            height = height_map[str(card.get("id", ""))]
            preferred_pages = [1, 0] if pages == 2 and card.get("kind") == "background" else list(range(pages))
            if report.get("reading_edition"):
                if card.get("original_quote") and card["original_item_id"] not in selected_ids:
                    continue
                if card.get("original_quote"):
                    preferred_pages = [1]
                else:
                    preferred_pages = list(range(pages)) if report.get("mode_report") and report.get("mode") == "quotes" else [0]
            if pages == 2 and report["variant"] == "episodes" and card.get("kind") == "background":
                preferred_pages = [1]
            for page in preferred_pages:
                column = min(range(2), key=lambda index: used[page][index])
                if used[page][column] + height <= capacities[page]:
                    columns[page][column].append(card)
                    used[page][column] += height
                    selected_ids.add(card["id"])
                    break
        selected = sum(not card.get("original_quote") for page in columns for column in page for card in column)
        content = _document(report, columns, selected, len(all_cards) - selected, base_url)
        browser.set_html(content)
        final = browser.measure()
        if any(page["overflow"] or max(page["columns"]) > page["available"] + 1 for page in final["pages"]):
            raise RuntimeError("报告内容超出纸面，请减少单块内容后再导出。")
        pdf = browser.pdf()
        if len(re.findall(rb"/Type\s*/Page\b", pdf)) != pages:
            raise RuntimeError("实际 PDF 页数与预览不一致，报告未导出。")
        return content, pdf


def _arguments(report, pages, base_url):
    if pages not in (1, 2):
        raise ValueError("报告只支持一页或两页。")
    if report.get("variant") not in VARIANT_NAMES:
        raise ValueError("未知报告版式。")
    return json.dumps(report, ensure_ascii=False, sort_keys=True), pages, base_url


def render_report_html(report, pages=1, base_url="http://localhost:3002"):
    """返回与 PDF 同一精选内容的 A4 HTML，不重新调用模型。"""
    return _prepare(*_arguments(report, pages, base_url))[0]


def create_report_pdf(report, pages=1, base_url="http://localhost:3002"):
    """用已测量分页的固定 HTML/CSS 创建一页或两页 PDF。"""
    return _prepare(*_arguments(report, pages, base_url))[1]
