from app.api.tasks import _task_status_query


def test_task_status_query_supports_comma_separated_statuses():
    assert _task_status_query("pending,processing") == {
        "$in": ["pending", "processing"]
    }


def test_task_status_query_keeps_single_status_as_string():
    assert _task_status_query("failed") == "failed"
