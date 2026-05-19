import requests

from app.services.transcript_fetcher import TranscriptFetcher


class FakeResponse:
    def __init__(self, text, status_code=200, headers=None):
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} error")


def test_fetch_transcript_detects_vtt_from_content_type_without_extension(monkeypatch):
    content = "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello world from a caption file.\n"

    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: FakeResponse(content, headers={"Content-Type": "text/vtt"}),
    )

    text, error = TranscriptFetcher.fetch_transcript("https://example.com/transcript")

    assert error is None
    assert "Hello world from a caption file" in text


def test_fetch_transcript_detects_srt_from_plain_text_body(monkeypatch):
    content = "1\n00:00:00,000 --> 00:00:02,000\nHello from SRT captions.\n"

    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: FakeResponse(content, headers={"Content-Type": "text/plain"}),
    )

    text, error = TranscriptFetcher.fetch_transcript("https://example.com/transcript")

    assert error is None
    assert "Hello from SRT captions" in text


def test_fetch_transcript_detects_json_from_plain_text_body(monkeypatch):
    content = '{"segments": [{"text": "First JSON segment."}, {"text": "Second JSON segment."}]}'

    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: FakeResponse(content, headers={"Content-Type": "text/plain"}),
    )

    text, error = TranscriptFetcher.fetch_transcript("https://example.com/transcript")

    assert error is None
    assert text == "First JSON segment. Second JSON segment."


def test_fetch_transcript_returns_clear_error_for_unknown_format(monkeypatch):
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: FakeResponse("not a transcript", headers={"Content-Type": "text/plain"}),
    )

    text, error = TranscriptFetcher.fetch_transcript("https://example.com/transcript")

    assert text is None
    assert "Could not determine transcript format" in error


def test_fetch_transcript_rejects_generic_html_page(monkeypatch):
    content = """
    <!doctype html>
    <html>
      <head><title>Episode Page</title></head>
      <body>
        <main>
          <h1>Podcast episode</h1>
          <p>Listen now, subscribe, and check out our sponsors.</p>
        </main>
      </body>
    </html>
    """

    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: FakeResponse(content, headers={"Content-Type": "text/html"}),
    )

    text, error = TranscriptFetcher.fetch_transcript("https://example.com/episode")

    assert text is None
    assert "Could not determine transcript format" in error


def test_fetch_transcript_parses_html_transcript_page(monkeypatch):
    content = """
    <!doctype html>
    <html>
      <head><title>Transcript</title><script>ignored()</script></head>
      <body>
        <nav>Navigation should be ignored</nav>
        <article>
          <h1>Podcast Transcript</h1>
          <p><strong>Host:</strong> Welcome to the episode.</p>
          <p>00:01:02 Guest: This is useful transcript text.</p>
          <p>[Music]</p>
        </article>
      </body>
    </html>
    """

    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: FakeResponse(content, headers={"Content-Type": "text/html"}),
    )

    text, error = TranscriptFetcher.fetch_transcript("https://example.com/episode-transcript")

    assert error is None
    assert "Welcome to the episode" in text
    assert "This is useful transcript text" in text
    assert "Host: Welcome to the episode.\n\nGuest: This is useful transcript text." in text
    assert "Navigation should be ignored" not in text


def test_fetch_transcript_compacts_lex_style_speaker_blocks(monkeypatch):
    content = """
    <!doctype html>
    <html>
      <body>
        <article>
          <p>This is a transcript of Lex Fridman Podcast #496.</p>
          <p>Table of Contents</p>
          <p>Introduction</p>
          <p>Lex Fridman</p>
          <p>(00:00:31)</p>
          <p>FFmpeg is probably one of the biggest CPU users in the world.</p>
          <p>Video codecs</p>
          <p>Jean-Baptiste Kempf</p>
          <p>(00:00:45)</p>
          <p>FFmpeg has one hundred thousand lines of assembly.</p>
        </article>
      </body>
    </html>
    """

    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: FakeResponse(content, headers={"Content-Type": "text/html"}),
    )

    text, error = TranscriptFetcher.fetch_transcript("https://example.com/ffmpeg-transcript")

    assert error is None
    assert text.startswith("Lex Fridman (00:00:31)")
    assert "Table of Contents" not in text
    assert "Video codecs\n\nJean-Baptiste" not in text
    assert "Jean-Baptiste Kempf (00:00:45)" in text


def test_fetch_transcript_result_extracts_html_timestamps_and_speakers(monkeypatch):
    content = """
    <!doctype html>
    <html>
      <body>
        <article>
          <p>This is a transcript of Lex Fridman Podcast #496.</p>
          <p>Table of Contents</p>
          <p>Introduction</p>
          <p>Lex Fridman</p>
          <p>(00:00:31)</p>
          <p>FFmpeg is probably one of the biggest CPU users in the world.</p>
          <p>Video codecs</p>
          <p>Jean-Baptiste Kempf</p>
          <p>(00:00:45)</p>
          <p>FFmpeg has one hundred thousand lines of assembly.</p>
        </article>
      </body>
    </html>
    """

    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: FakeResponse(content, headers={"Content-Type": "text/html"}),
    )

    result, error = TranscriptFetcher.fetch_transcript_result("https://example.com/ffmpeg-transcript")

    assert error is None
    assert result.format == "html"
    assert result.confidence >= 0.8
    assert result.segments == [
        {
            "speaker": "Lex Fridman",
            "time": "00:00:31",
            "start": 31,
            "text": "FFmpeg is probably one of the biggest CPU users in the world.",
        },
        {
            "speaker": "Jean-Baptiste Kempf",
            "time": "00:00:45",
            "start": 45,
            "text": "FFmpeg has one hundred thousand lines of assembly.",
        },
    ]


def test_fetch_transcript_result_extracts_inline_timestamp_patterns(monkeypatch):
    content = """
    <!doctype html>
    <html>
      <body>
        <article>
          <h1>Episode Transcript</h1>
          <p>00:01:02 Host: Welcome to the episode.</p>
          <p>Guest (00:01:05)</p>
          <p>This is the second segment.</p>
          <p>[00:01:09] Closing line without speaker.</p>
        </article>
      </body>
    </html>
    """

    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: FakeResponse(content, headers={"Content-Type": "text/html"}),
    )

    result, error = TranscriptFetcher.fetch_transcript_result("https://example.com/transcript")

    assert error is None
    assert result.segments[0]["speaker"] == "Host"
    assert result.segments[0]["start"] == 62
    assert result.segments[1]["speaker"] == "Guest"
    assert result.segments[1]["time"] == "00:01:05"
    assert result.segments[2]["time"] == "00:01:09"
    assert "speaker" not in result.segments[2]
