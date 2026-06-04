"""
Celery package for Hiremate background workers.

Entry point for CLI:
  celery -A backend.celery.app worker ...
"""
from backend.celery.app import celery_app

__all__ = ["celery_app"]
