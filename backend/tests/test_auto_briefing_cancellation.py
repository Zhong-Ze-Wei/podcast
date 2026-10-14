from datetime import datetime, timedelta, timezone

from tests.test_briefing_auto_reporter import setup


def test_user_cancelled_auto_report_stays_cancelled_for_that_period(setup):
    db, user, reporter, queue, generated, modes = setup
    now = datetime(2026, 10, 4, 16, 5, tzinfo=timezone.utc)
    identifier, = reporter.check_due(now)
    queue.tasks[identifier]["status"] = "cancelled"

    assert reporter.check_due(now + timedelta(minutes=5)) == []
    run = db.briefing_auto_runs.find_one({"owner_id": str(user["_id"])})
    assert run["status"] == "cancelled"
    assert run["attempts"] == 1
    assert reporter.check_due(now + timedelta(hours=2)) == []
    assert len(queue.tasks) == 1
    assert generated == []

    # 取消当前周期，不关闭之后周期的自动简报。
    following, = reporter.check_due(now + timedelta(days=7))
    assert following != identifier
