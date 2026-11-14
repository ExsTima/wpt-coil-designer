"""
Modular tab views for the WPT Coil Designer GUI.
"""

from .distance_tab import DistanceSweepTab
from .femm_tab import FemmTab
from .field_2d_tab import Field2DTab
from .field_3d_tab import Field3DTab
from .frequency_tab import FrequencySweepTab
from .input_tab import InputTab
from .results_tab import ResultsTab

__all__ = [
    "InputTab",
    "ResultsTab",
    "DistanceSweepTab",
    "FrequencySweepTab",
    "Field2DTab",
    "Field3DTab",
    "FemmTab",
]
