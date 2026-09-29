from bson import ObjectId

from app.api.transcripts import transcripts_bp
from tests.auth_helpers import add_user, auth_headers, make_auth_app


def _add_episode_and_transcript(db, owner_id):
    episode_id = ObjectId()
    db.episodes._data.append({
        "_id": episode_id,
        "owner_id": owner_id,
        "title": "Private Episode",
        "status": "transcribed",
    })
    db.transcripts._data.append({
        "_id": ObjectId(),
        "owner_id": owner_id,
        "episode_id": episode_id,
        "text": "private transcript",
        "segments": [],
        "created_at": None,
    })
    return episode_id


def test_transcript_read_and_delete_are_owner_filtered():
    app = make_auth_app((transcripts_bp, "/api/transcripts"))
    user1 = add_user(app.db, "user1@example.com")
    user2 = add_user(app.db, "user2@example.com")
    episode_id = _add_episode_and_transcript(app.db, str(user1["_id"]))
    client = app.test_client()

    own = client.get(f"/api/transcripts/{episode_id}", headers=auth_headers(user1))
    other = client.get(f"/api/transcripts/{episode_id}", headers=auth_headers(user2))
    delete_other = client.delete(f"/api/transcripts/{episode_id}", headers=auth_headers(user2))

    assert own.status_code == 200
    assert other.status_code == 200
    assert delete_other.status_code == 200
    assert app.db.transcripts.find_one({"episode_id": episode_id}) is None  # member 可删（共享库）
