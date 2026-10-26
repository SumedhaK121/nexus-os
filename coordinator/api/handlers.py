"""Compatibility shim for API handler registration.
Delegates to modular handler packages in coordinator/api/.
"""

from coordinator.api import core_handlers
from coordinator.api import resource_handlers
from coordinator.api import file_handlers
from coordinator.api import sync_handlers
from coordinator.api import clock_handlers
from coordinator.api import ops_handlers


def install(coord):
    """Register all API handler modules on the coordinator instance."""
    core_handlers.register(coord)
    resource_handlers.register(coord)
    file_handlers.register(coord)
    sync_handlers.register(coord)
    clock_handlers.register(coord)
    ops_handlers.register(coord)
