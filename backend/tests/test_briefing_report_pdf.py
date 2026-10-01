"""PDF 以实际 Chrome 字体测量、页数和来源完整性验证，避免只检查模板字符串。"""
import re
from html.parser import HTMLParser
from unittest.mock import Mock

import pytest

from app.services.briefing_report_pdf import create_report_pdf, render_report_html, _chrome_path, _wait_debugger_address, _PrintBrowser


class ReportParser(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.cards = []
        self.counts = {}
        self.links = []
        self.source_index = []
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "body":
            self.counts = {"selected": int(attrs["data-selected-count"]), "omitted": int(attrs["data-omitted-count"])}
        if tag == "article":
            self.cards.append(attrs["data-card-id"])
        if tag == "a":
            self.links.append(attrs.get("href"))
        if attrs.get("class") == "index-item":
            self.source_index.append(attrs["data-source-id"])


def example_report(variant):
    sources = [{
        "id": f"S{i + 1:02}", "episode_id": f"episode-{i}", "feed": f"播客节目 {i + 1}",
        "title": "从技术变化到日常工作的实践：嘉宾谈今天的具体经验与问题",
        "url": f"https://www.youtube.com/watch?v=source{i}",
    } for i in range(10)]
    kinds = ("concept", "quote", "resource", "background")
    cards = []
    for i in range(12):
        for kind in kinds:
            source = sources[i % 10]
            cards.append({
                "id": f"{kind}-{i}", "kind": kind, "title": {
                    "concept": "反向半人马：人替机器收拾错误",
                    "quote": "先理解事实，再选择方法", "resource": "节目里提到的工作笔记",
                    "background": "嘉宾背景：研究与写作经历",
                }[kind],
                "text": "这一段谈到工作责任的分配，以及实际采用工具后怎样检查和处理错误。" if kind != "quote" else "",
                "quote": "我们需要先了解具体事实，再选择能够通过实际工作验证的方法。",
                "context": "嘉宾回顾了自己使用工具时遇到的困难，并解释责任边界。",
                "source_id": source["id"], "episode_id": source["episode_id"],
                "start": 2495, "end": 2515, "speaker": "测试嘉宾",
                "url": "https://example.com/article" if kind == "resource" else "",
            })
    if variant == "episodes":
        cards = [{
            "id": f"episode-{i}", "kind": "episode", "title": source["title"],
            "text": "本期回顾了工具变化给工作带来的实际影响。", "source_id": source["id"],
            "episode_id": source["episode_id"], "children": [cards[i * 4], cards[i * 4 + 1]],
        } for i, source in enumerate(sources)]
    return {
        "id": f"report-{variant}", "variant": variant, "title": "这一期，记下新词与原话",
        "generated_at": "2026-09-30T18:00:00+00:00", "coverage": {"sources": 10, "characters": 281782},
        "sources": sources, "sections": [{"id": "main", "items": cards}],
    }


@pytest.fixture(scope="module", autouse=True)
def installed_chrome():
    try:
        _chrome_path()
    except RuntimeError:
        pytest.skip("实际 PDF 页数验证需要已安装 Chrome")


@pytest.mark.parametrize("variant", ["overview", "episodes", "concepts", "quotes", "resources"])
@pytest.mark.parametrize("pages", [1, 2])
def test_actual_pages_match_preview_and_keep_complete_citations(variant, pages, tmp_path):
    report = example_report(variant)
    content = render_report_html(report, pages)
    pdf = create_report_pdf(report, pages)
    parser = ReportParser(content)
    tmp_path.joinpath(f"{variant}-{pages}.pdf").write_bytes(pdf)
    assert pdf.startswith(b"%PDF-")
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) == pages
    assert parser.counts["selected"] > 0
    top_count = len(report["sections"][0]["items"])
    assert parser.counts["selected"] + parser.counts["omitted"] == top_count
    assert "2026-10-01" in content  # 用户香港时区，不取 Windows 宿主默认日期。
    assert any("/episodes/episode-" in link and "t=2495" in link for link in parser.links)
    assert "41:35" in content
    assert "播客节目" in content
    if pages == 2:
        assert "本次材料索引" in content
        assert all(source["title"] in content for source in report["sources"])


def test_oversized_quote_is_omitted_whole_with_visible_count():
    report = example_report("quotes")
    cards = report["sections"][0]["items"]
    quotes = [card for card in cards if card["kind"] == "quote"]
    quotes[0]["quote"] = "很长的一段原话必须完整保留，不能截断给用户错误的印象。" * 300
    report["sections"][0]["items"] = quotes[:3]
    content = render_report_html(report)
    parser = ReportParser(content)
    assert quotes[0]["id"] not in parser.cards
    assert parser.counts == {"selected": 2, "omitted": 1}
    assert "另有 1 块留在网页" in content
    assert quotes[1]["quote"] in content


def test_user_content_is_escaped_and_script_urls_are_not_linked():
    report = example_report("resources")
    card = next(card for card in report["sections"][0]["items"] if card["kind"] == "resource")
    card["title"] = '<script>alert("unsafe")</script>'
    card["url"] = "javascript:alert(1)"
    content = render_report_html(report)
    assert "<script>" not in content
    assert "&lt;script&gt;" in content
    assert "javascript:" not in content


def test_unsupported_pages_rejected_without_starting_browser():
    with pytest.raises(ValueError, match="一页或两页"):
        create_report_pdf(example_report("quotes"), pages=3)


def test_print_quote_uses_full_labelled_translation_and_links_original():
    report = example_report("quotes")
    card = next(card for card in report["sections"][0]["items"] if card["kind"] == "quote")
    card["quote"] = "An exact English source quotation that remains available in the saved transcript."
    card["translation"] = "这段完整的中文译文在纸面上展示，英文原句可以通过节目文稿回看。"
    report["sections"][0]["items"] = [card]
    content = render_report_html(report)
    assert card["translation"] in content
    assert card["quote"] not in content
    assert "译文 · 原句见节目文稿" in content
    assert "watch?v=source0&amp;t=2495" in content
    assert content.count('target="_blank"') == len(ReportParser(content).links)


def test_two_pages_reserves_a_background_with_publisher_and_retrieval_date():
    report = example_report("overview")
    card = next(card for card in report["sections"][0]["items"] if card["kind"] == "background")
    card.update(relation="external", publisher="嘉宾官方介绍", accessed_at="2026-10-01T03:00:00Z")
    content = render_report_html(report, pages=2)
    assert card["id"] in ReportParser(content).cards
    assert "补充背景" in content
    assert "嘉宾官方介绍 · 查阅于 2026-10-01" in content


def test_debugger_waits_for_readable_complete_port_file(monkeypatch):
    active_port = Mock()
    active_port.read_text.side_effect = [
        FileNotFoundError(), PermissionError("Chrome 正在写入端口文件"),
        "43123\n", "43123\n/devtools/browser/session\n",
    ]
    process = Mock()
    process.poll.return_value = None
    monkeypatch.setattr("app.services.briefing_report_pdf.time.sleep", lambda _: None)
    assert _wait_debugger_address(active_port, process) == ["43123", "/devtools/browser/session"]
    assert active_port.read_text.call_count == 4


def test_overview_two_pages_keeps_all_three_content_types():
    report = example_report("overview")
    content = render_report_html(report, pages=2)
    assert all(f'class="card {kind}-card"' in content for kind in ("concept", "quote", "resource"))


def test_two_page_episode_report_selects_at_least_four_actual_episodes():
    report = example_report("episodes")
    all_resources = [card for card in example_report("resources")["sections"][0]["items"] if card["kind"] == "resource"]
    for index, card in enumerate(report["sections"][0]["items"]):
        card["children"].append(all_resources[index])
    backgrounds = [card for card in example_report("overview")["sections"][0]["items"] if card["kind"] == "background"][:2]
    report["sections"][0]["items"].extend(backgrounds)
    content = render_report_html(report, pages=2)
    assert content.count('class="card episode-card"') >= 4
    assert "本次材料索引" in content
    first_page = content.split('data-page="1"', 1)[1].split('data-page="2"', 1)[0]
    assert 'class="card background-card"' not in first_page


@pytest.mark.parametrize("pages", [1, 2])
def test_reading_edition_exports_all_five_quotes_with_short_context(pages):
    report = example_report("quotes")
    quotes = [card for card in report["sections"][0]["items"] if card["kind"] == "quote"][:5]
    for quote in quotes:
        quote.update(title="", brief="谈实际工作中的责任边界。")
    report.update(reading_edition=True, sections=[{"id": "quotes", "items": quotes}])

    content = render_report_html(report, pages=pages, base_url="http://localhost:3002")
    assert ReportParser(content).counts == {"selected": 5, "omitted": 0}
    assert 'class="reading-edition"' in content
    assert "<h2></h2>" not in content
    assert quotes[0]["context"] not in content
    assert "谈实际工作中的责任边界。" in content
    pdf = create_report_pdf(report, pages=pages, base_url="http://localhost:3002")
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) == pages


def test_reading_two_pages_adds_exact_originals_and_material_sources():
    report = example_report("quotes")
    quotes = [card for card in report["sections"][0]["items"] if card["kind"] == "quote"][:3]
    for index, quote in enumerate(quotes):
        quote.update(title="", brief="谈工具变化对工作的影响。",
                     quote=f"The exact original quotation from the programme, with its full sentence preserved {index}.",
                     translation="工具正在改变工作，原话需要结合具体语境阅读。")
    report.update(reading_edition=True, sections=[{"id": "quotes", "items": quotes}],
                  threads=[{"text": "两期节目都谈到了学习工具所需的投入。", "supporting_item_ids": [quotes[0]["id"], quotes[1]["id"]]}])

    content = render_report_html(report, pages=2)
    first_page, second_page = content.split('data-page="2"', 1)
    assert all(quote["translation"] in first_page and quote["quote"] not in first_page for quote in quotes)
    assert all(quote["quote"] in second_page for quote in quotes)
    assert "原话对照与材料来源" in second_page
    assert "共同谈到 · AI 归纳" in second_page
    assert second_page.index("本次材料索引") < second_page.index('class="columns"')
    assert ReportParser(content).counts == {"selected": 3, "omitted": 0}
    pdf = create_report_pdf(report, pages=2)
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) == 2


def test_content_quote_mode_continues_primary_quotes_on_page_two_while_legacy_does_not():
    report = example_report("quotes")
    quotes = [card for card in report["sections"][0]["items"] if card["kind"] == "quote"][:10]
    for quote in quotes:
        quote.update(title="", brief="谈实际工作中的责任边界。", quote=quote["quote"] * 4)
    report.update(reading_edition=True, sections=[{"id": "quotes", "items": quotes}])
    legacy_html = render_report_html(report, pages=2)
    legacy_second = legacy_html.split('data-page="2"', 1)[1]
    assert 'class="card quote-card"' not in legacy_second
    assert "原话对照与材料来源" in legacy_second

    report.update(mode_report=True, mode="quotes")
    mode_html = render_report_html(report, pages=2)
    mode_second = mode_html.split('data-page="2"', 1)[1]
    assert 'class="card quote-card"' in mode_second
    assert "更多原话与材料来源" in mode_second
    assert ReportParser(mode_html).counts["selected"] > ReportParser(legacy_html).counts["selected"]
    assert all(quote["quote"] in mode_html for quote in quotes if quote["id"] in ReportParser(mode_html).cards)


def test_reading_original_that_cannot_fit_is_omitted_whole_with_count():
    report = example_report("quotes")
    quote = next(card for card in report["sections"][0]["items"] if card["kind"] == "quote")
    quote.update(title="", brief="谈实际工作的责任边界。", quote="A long complete quotation cannot be cut in the middle. " * 300,
                 translation="这句话的中文译文可以在首页完整显示。")
    report.update(reading_edition=True, sections=[{"id": "quotes", "items": [quote]}])

    content = render_report_html(report, pages=2)
    assert ReportParser(content).counts == {"selected": 1, "omitted": 0}
    assert quote["quote"] not in content
    assert "英文原话对照 0/1 句，完整原话见文稿" in content


def test_reading_pdf_omits_common_thread_when_its_evidence_cannot_fit():
    report = example_report("quotes")
    quotes = [card for card in report["sections"][0]["items"] if card["kind"] == "quote"][:3]
    quotes[0]["quote"] *= 300
    thread_text = "这句话需要两期原话共同支撑，不能在只选到一期时出现。"
    report.update(reading_edition=True, sections=[{"id": "quotes", "items": quotes}],
                  threads=[{"text": thread_text, "supporting_item_ids": [quotes[0]["id"], quotes[1]["id"]]}])

    content = render_report_html(report, pages=2)
    assert ReportParser(content).counts == {"selected": 2, "omitted": 1}
    assert quotes[0]["quote"] not in content
    assert thread_text not in content


@pytest.mark.parametrize("style,columns,background,quote_size", [
    ("paper", 1, "rgb(243, 240, 233)", "23px"),
    ("newspaper", 2, "rgb(244, 237, 220)", "24px"),
])
@pytest.mark.parametrize("pages", [1, 2])
def test_shared_print_styles_have_actual_columns_readable_type_and_exact_pages(style, columns, background, quote_size, pages):
    report = example_report("quotes")
    quotes = [card for card in report["sections"][0]["items"] if card["kind"] == "quote"][:10]
    for quote in quotes:
        quote.update(title="", brief="谈工作中的责任边界。")
    report.update(mode_report=True, mode="quotes", reading_edition=True,
                  sections=[{"id": "quotes", "items": quotes}])
    content = render_report_html(report, pages, style=style)
    parser = ReportParser(content)
    assert parser.counts["selected"] > 0
    assert parser.counts["selected"] + parser.counts["omitted"] == len(quotes)
    assert all(quote["quote"] in content for quote in quotes if quote["id"] in parser.cards)
    pdf = create_report_pdf(report, pages, style=style)
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) == pages
    with _PrintBrowser() as browser:
        browser.set_html(content)
        appearance = browser.command("Runtime.evaluate", {"expression": """(() => ({
          columns: [...document.querySelectorAll('.report-page')].map(page => page.querySelectorAll('.column').length),
          background: getComputedStyle(document.querySelector('.report-page')).backgroundColor,
          quoteSize: getComputedStyle(document.querySelector('blockquote')).fontSize,
          cardBorder: getComputedStyle(document.querySelector('.card')).borderLeftWidth
        }))()""", "returnByValue": True}, session=True)["result"]["value"]
        assert appearance == {"columns": [columns] * pages, "background": background,
                              "quoteSize": quote_size, "cardBorder": "0px"}
        metrics = browser.measure()
        assert all(not page["overflow"] and max(page["columns"]) <= page["available"] + 1 for page in metrics["pages"])
    if pages == 2:
        assert 'class="card quote-card"' in content.split('data-page="2"', 1)[1]
        second_page = content.split('data-page="2"', 1)[1]
        assert second_page.index('class="columns"') < second_page.index("本次材料索引")


@pytest.mark.parametrize("style", ["paper", "newspaper"])
def test_monthly_print_index_only_lists_included_sources_with_exact_boundary_and_period_link(style):
    report = example_report("overview")
    sources = [{"id": f"S{i}", "episode_id": f"episode-{i}", "feed": f"播客 {i}",
                "title": "完整节目标题" + ("与一段需要换行的较长说明" * (i % 6)),
                "url": f"https://example.com/episode-{i}"} for i in range(200)]
    cards = [{"id": f"core-{i}", "kind": "insight", "title": f"判断 {i}",
              "text": "具体的判断来自本期的实际讨论。", "source_id": sources[i]["id"],
              "episode_id": sources[i]["episode_id"], "start": 61} for i in range(20)]
    report.update(mode_report=True, mode="core", sources=sources, coverage={"sources": 200},
                  sections=[{"id": "core", "items": cards}], interests=["AI", "LLM"],
                  period={"type": "month", "start": "2026-09-01", "label": "2026年9月 · 9月1日—9月30日",
                          "total_count": 250, "transcript_count": 200})
    content = render_report_html(report, pages=2, style=style)
    parser = ReportParser(content)
    selected_sources = {card["source_id"] for card in cards if card["id"] in parser.cards}
    assert set(parser.source_index).issubset(selected_sources)
    assert 0 < len(parser.source_index) <= 8
    assert f"PDF 收录 {len(selected_sources)} 期 · 相关文稿 200 期 · 未收录 {200 - len(selected_sources)} 期" in content
    assert f"索引未列 {len(selected_sources) - len(parser.source_index)} 期收录来源" in content
    assert parser.counts["selected"] + parser.counts["omitted"] == len(cards)
    assert "2026年9月 · 9月1日—9月30日" in content
    assert "关注：AI、LLM" in content
    assert "200 期相关节目" in content
    assert "本期 250 期 / 200 期有文稿" in content
    assert "http://localhost:3002/briefing?period_type=month&period_start=2026-09-01" in parser.links
    assert "http://localhost:3002/episodes/episode-0?t=61" in parser.links
    assert len(re.findall(rb"/Type\s*/Page\b", create_report_pdf(report, pages=2, style=style))) == 2


def test_print_style_changes_cache_identity_and_invalid_style_never_opens_browser(monkeypatch):
    report = example_report("resources")
    paper = render_report_html(report, style="paper")
    newspaper = render_report_html(report, style="newspaper")
    assert 'class="report-style-paper"' in paper
    assert 'class="report-style-newspaper"' in newspaper
    assert paper != newspaper
    monkeypatch.setattr("app.services.briefing_report_pdf._PrintBrowser", Mock(side_effect=AssertionError("不应启动浏览器")))
    with pytest.raises(ValueError, match="未知报告风格"):
        create_report_pdf(report, style="unsupported")


def test_quote_mode_measures_full_report_instead_of_only_homepage_six_items():
    report = example_report("quotes")
    quotes = [card for card in report["sections"][0]["items"] if card["kind"] == "quote"][:7]
    for quote in quotes[:6]:
        quote["quote"] *= 300
    quotes[6].update(title="", brief="谈具体的工作方法。")
    report.update(mode_report=True, mode="quotes", reading_edition=True,
                  sections=[{"id": "quotes", "items": quotes}])
    content = render_report_html(report, style="paper")
    assert ReportParser(content).counts == {"selected": 1, "omitted": 6}
    assert quotes[6]["quote"] in content
