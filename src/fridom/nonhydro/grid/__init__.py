"""
Module that stores all available grids for the non-hydrostatic model.
"""
from typing import TYPE_CHECKING
from lazypimp import setup

# ================================================================
#  Disable lazy loading for type checking
# ================================================================
if TYPE_CHECKING:
    # import modules
    from . import cartesian

    # import classes
    from fridom.framework.grid import AxisPosition, Position, TransformType

# ================================================================
#  Setup lazy loading
# ================================================================
base = "fridom.nonhydro.grid"

all_modules_by_origin = { base: ["cartesian"] }

all_imports_by_origin = {
    "fridom.framework.grid": ["AxisPosition", "Position", "TransformType"]
}

setup(__name__, all_modules_by_origin, all_imports_by_origin)
