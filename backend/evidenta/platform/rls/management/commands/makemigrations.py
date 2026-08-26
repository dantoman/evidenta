"""`makemigrations`, which cannot run under the query guard without help.

Django's own command calls ``check_consistent_history()`` inline in ``handle()``,
and that reads ``django_migrations`` on the application connection. The guard
refuses it, correctly: there is no tenant context, and it cannot know this
particular query is a schema question rather than a business one.

The exemption covers the whole command rather than a single query, because the
offending call is made inside Django's ``handle()`` and there is no seam to wrap
more narrowly. That is wider than the project prefers, and acceptable for exactly
one reason: this command never runs in a request or a task. It is a developer
tool that writes files.

Recorded in `docs/PROGRESS.md` as an undecided papercut since 2026-08-25, hit by
two sessions; migrations were being hand-written to get around it, which is worse
than this exemption -- a hand-written migration is not checked against the models
at all.
"""

from __future__ import annotations

from typing import Any

from django.core.management.commands.makemigrations import Command as BaseCommand

from evidenta.platform.rls.context import unguarded


class Command(BaseCommand):
    def handle(self, *app_labels: Any, **options: Any) -> Any:
        with unguarded("makemigrations: consistency check reads django_migrations"):
            return super().handle(*app_labels, **options)
