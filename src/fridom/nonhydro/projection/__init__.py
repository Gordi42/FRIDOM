"""
# Projection module for the nonhydrostatic model
The projection routines are used for flow decomposition. E.g. to
decompose the flow into geostrophic and ageostrophic components,
or to decompose the flow into balanced and unbalanced components.

## Linear Projections:
    - WaveSpectral          : Projection onto the linear wave mode
    - GeostrophicSpectral   : Projection onto the geostrophic mode
    - GeostrophicTimeAverage: Projection onto the geo. mode using a time average
    - DivergenceSpectral    : Projection onto the divergence mode

## Nonlinear Projections:
    - OptimalBalance        : Balancing using the optimal balance method
    - NNMD                  : Balancing using nonlinear normal mode decomposition
"""
import sys
from types import ModuleType
import importlib
from typing import TYPE_CHECKING

# ================================================================
#  Disable lazy loading for type checking
# ================================================================
if TYPE_CHECKING:
    from .divergence_spectral import DivergenceSpectral
    from .geostrophic_spectral import GeostrophicSpectral
    from .wave_spectral import WaveSpectral
    from fridom.framework.projection import GeostrophicTimeAverage

    from .nnmd import NNMD
    from fridom.framework.projection import OptimalBalance

# ================================================================
#  Define all the possible imports
# ================================================================

# Set up dictionary that maps an import to a path
# items in the all_modules_by_origin dictionary are imported as modules
all_modules_by_origin = { }

# items in the all_imports_by_origin dictionary are imported as elements of a module
base_path = "fridom.nonhydro.projection"
fr_base_path = "fridom.framework.projection"
all_imports_by_origin = {
    f"{base_path}.wave_spectral": ["WaveSpectral"],
    f"{base_path}.geostrophic_spectral": ["GeostrophicSpectral"],
    f"{fr_base_path}.geostrophic_time_average": ["GeostrophicTimeAverage"],
    f"{base_path}.divergence_spectral": ["DivergenceSpectral"],
    f"{fr_base_path}.optimal_balance": ["OptimalBalance"],
    f"{base_path}.nnmd": ["NNMD"],
}

# ================================================================
#  Set up the import system
# ================================================================

origins = {}
_all_modules = []
for origin, items in all_modules_by_origin.items():
    for item in items:
        _all_modules.append(item)
        origins[item] = origin

_all_imports = []
for origin, items in all_imports_by_origin.items():
    for item in items:
        _all_imports.append(item)
        origins[item] = origin

# load submodules on demand
class _module(ModuleType):
    def __getattr__(self, name):
        # check if the attribute is a module
        if name in _all_modules:
            res = importlib.import_module(origins[name] + "." + name)
        # check if the attribute is an import
        elif name in _all_imports:
            mod = importlib.import_module(origins[name])
            res = getattr(mod, name)
        # if the attribute is not found
        else:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
        # set the attribute in the current module such that it is not loaded again
        setattr(self, name, res)
        # return the attribute
        return res

sys.modules[__name__].__class__ = _module
__all__ = _all_modules + _all_imports
