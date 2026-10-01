"""简报任务按账号与自然周期去重，不让其他周期互相阻塞。"""


def report_task_conflicts(task, owner_id, period=None):
    if task.get("owner_id") != owner_id or task.get("status") not in ("pending", "processing"):
        return False
    task_period = task.get("report_period")
    # 旧任务没有周期记录，完成前仍保留原来的去重规则。
    if period is None or task_period is None:
        return True
    return task_period["type"] == period["type"] and task_period["start"] == period["start"]
