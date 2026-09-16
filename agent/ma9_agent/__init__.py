"""MA9 runtime decision layer.

The package deliberately keeps recognition, policy, and controller integration
separate so the policy can be tested without a running emulator.
"""

from .models import League, Rect, VehicleObservation
from .race_controller import RaceController, ScreenState
from .runtime_config import RuntimeConfig
from .vehicle_selector import PageTracker, VehicleSelector

__all__ = [
    "League",
    "PageTracker",
    "RaceController",
    "Rect",
    "RuntimeConfig",
    "ScreenState",
    "VehicleObservation",
    "VehicleSelector",
]
