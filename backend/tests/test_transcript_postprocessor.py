from app.services.transcript_postprocessor import normalize_transcript


def test_normalize_transcript_removes_spaces_between_chinese_characters():
    text, segments, metadata = normalize_transcript(
        "这 是 一 个 中文 播 客 ， 很 好 。",
        [{"text": "你 好 ， 世界 。"}],
        language="zh",
    )

    assert text == "这是一个中文播客，很好。"
    assert segments[0]["text"] == "你好，世界。"
    assert metadata["ai_normalized"] is False


def test_normalize_transcript_keeps_english_word_spacing():
    text, segments, _ = normalize_transcript(
        "今天 聊 OpenAI API 和 GPU",
        [{"text": "模型 是 GPT-4o mini"}],
        language="zh",
    )

    assert text == "今天聊 OpenAI API 和 GPU"
    assert segments[0]["text"] == "模型是 GPT-4o mini"
