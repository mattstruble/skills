"""Notification service for a task management app."""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class Task:
    id: str
    title: str
    assignee_email: str
    due_date: datetime
    status: str = "open"
    priority: int = 0
    created_at: datetime | None = None


class NotificationService:
    def __init__(self, task_repo, email_sender, clock=None):
        self.task_repo = task_repo
        self.email_sender = email_sender
        self.clock = clock or (lambda: datetime.now())

    def send_due_reminders(self) -> int:
        """Send email reminders for tasks due within 24 hours. Returns count sent."""
        now = self.clock()
        upcoming = self.task_repo.find_due_between(now, now + timedelta(hours=24))
        count = 0
        for task in upcoming:
            if task.status == "open":
                self.email_sender.send(
                    to=task.assignee_email,
                    subject=f"Reminder: '{task.title}' is due soon",
                    body=f"Your task '{task.title}' is due by {task.due_date}.",
                )
                count += 1
        return count

    def notify_overdue(self) -> list[str]:
        """Mark overdue tasks and notify assignees. Returns list of task IDs marked."""
        now = self.clock()
        overdue = self.task_repo.find_overdue(now)
        marked = []
        for task in overdue:
            if task.status == "open":
                task.status = "overdue"
                self.task_repo.save(task)
                self.email_sender.send(
                    to=task.assignee_email,
                    subject=f"Overdue: '{task.title}'",
                    body=f"Your task '{task.title}' was due on {task.due_date}.",
                )
                marked.append(task.id)
        return marked

    def escalate_high_priority(self, manager_email: str) -> int:
        """Escalate overdue high-priority tasks to manager. Returns count escalated."""
        now = self.clock()
        overdue = self.task_repo.find_overdue(now)
        count = 0
        for task in overdue:
            if task.priority >= 3 and task.status in ("open", "overdue"):
                self.email_sender.send(
                    to=manager_email,
                    subject=f"Escalation: '{task.title}' (P{task.priority})",
                    body=f"High-priority task '{task.title}' assigned to {task.assignee_email} is overdue.",
                )
                count += 1
        return count
