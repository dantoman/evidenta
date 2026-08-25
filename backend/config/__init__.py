"""Project configuration package.

Importing the Celery application here is the documented Django/Celery pattern: it
guarantees the app is loaded whenever Django starts, so ``@shared_task`` resolves.
"""

from config.celery import app as celery_app

__all__ = ("celery_app",)
