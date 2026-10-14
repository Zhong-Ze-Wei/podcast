"""简报任务按账号与自然周期去重，不让其他周期互相阻塞。"""
from threading import RLock


report_submission_lock = RLock()


def report_task_conflicts(task, owner_id, period=None):
    if task.get("owner_id") != owner_id or task.get("status") not in ("pending", "processing"):
        return False
    task_period = task.get("report_period")
    # 旧任务没有周期记录，完成前仍保留原来的去重规则。
    if period is None or task_period is None:
        return True
    return task_period["type"] == period["type"] and task_period["start"] == period["start"]


def submit_report_task(queue, *, owner_id, func, report_period=None, **options):
    """活动任务检查与登记处于同一短锁内，正文处理由队列执行。"""
    with report_submission_lock:
        if any(report_task_conflicts(task, owner_id, report_period)
               for status in ("pending", "processing")
               for task in queue.get_all_tasks(task_type="briefing-report", status=status, limit=0)):
            return None
        if report_period is not None:
            options["report_period"] = report_period
        return queue.submit(task_type="briefing-report", owner_id=owner_id, func=func, **options)
