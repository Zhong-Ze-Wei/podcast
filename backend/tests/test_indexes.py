from app import ensure_indexes


class RecordingCollection:
    def __init__(self):
        self.indexes = []

    def create_index(self, *args, **kwargs):
        self.indexes.append((args, kwargs))

    def list_indexes(self):
        return []

    def drop_index(self, name):
        pass


class RecordingDB:
    def __init__(self):
        self.feeds = RecordingCollection()
        self.users = RecordingCollection()
        self.episodes = RecordingCollection()
        self.transcripts = RecordingCollection()
        self.summaries = RecordingCollection()
        self.prompt_templates = RecordingCollection()
        self.tasks = RecordingCollection()
        self.briefings = RecordingCollection()


def test_tasks_completed_at_ttl_index_is_created():
    db = RecordingDB()

    ensure_indexes(db)

    assert any(
        args == ("completed_at",) and kwargs.get("expireAfterSeconds") == 7 * 24 * 60 * 60
        for args, kwargs in db.tasks.indexes
    )
