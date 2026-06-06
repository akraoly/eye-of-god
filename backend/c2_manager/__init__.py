"""C2Manager — Couche d'abstraction unifiée pour 19 frameworks C2."""
from c2_manager.core import C2ManagerEngine, c2_engine
from c2_manager.models import C2Type, C2Status, C2Config, Listener, Implant, Task, PayloadConfig
from c2_manager.webhooks.event_bus import event_bus, EventType

__all__ = [
    "C2ManagerEngine", "c2_engine",
    "C2Type", "C2Status", "C2Config",
    "Listener", "Implant", "Task", "PayloadConfig",
    "event_bus", "EventType",
]
