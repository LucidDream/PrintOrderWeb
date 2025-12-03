"""
Services layer for PrintOrderWeb.

This module contains the business logic services:
- InventoryService: Background inventory refresh thread
- JobService: Job submission threads and result store

Thread Model:
    Main Thread (Flask)
    ├── InventoryService thread (30-second refresh loop)
    └── JobService threads (one per job submission)

Each service creates its own ConsumableAPIClient instance,
ensuring complete thread isolation.
"""

from .inventory_service import InventoryService
from .job_service import JobService, JobResultStore

__all__ = [
    "InventoryService",
    "JobService",
    "JobResultStore",
]
