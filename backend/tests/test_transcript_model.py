from collections.abc import Generator

from bson import ObjectId

from app.models.transcript import Transcript


def test_transcript_create_materializes_generator_values():
    def words():
        yield {"word": "hello", "score": 0.9}

    doc = Transcript.create(
        episode_id=ObjectId(),
        text="hello",
        segments=[
            {
                "start": 0,
                "end": 1,
                "text": "hello",
                "words": words(),
            }
        ],
    )

    assert not isinstance(doc["segments"][0]["words"], Generator)
    assert doc["segments"][0]["words"] == [{"word": "hello", "score": 0.9}]
