"""
FRIDOM Framework
================

Description
-----------
This module contain the base classes and functions for the FRIDOM framework.
This module should mainly be used for developing new modules and models.

Modules
-------
'grid'
    Contains classes for grid generation
'domain_decomposition'
    Contains classes for domain decomposition (parallelization)
'config'
    Contains the configuration settings for the framework
'utils'
    Contains utility functions
'time_steppers'
    Contains classes related to time stepping
'modules'
    Contains the base class for modules
'projection'
    Contains functions for flow decomposition
'timing_module'
    Contains functions for timing the model (benchmarking)

Classes
-------
'ModelSettingsBase'
    Base class for model settings
'FieldVariable'
    Class for storing scalar variables
'StateBase'
    Base class for storing state variables
'ModelState'
    Class for storing model state variables
'Model'
    Main class for models
'DiagnoseImbalanceBase'
    Base class for diagnosing imbalances
'MeshPoint'
    Enum class for the different types of mesh points

Functions
'to_numpy(x)'
    returns a deepcopy of x where all cupy arrays are converted to numpy arrays

"""
import sys
from types import ModuleType
import importlib
from typing import TYPE_CHECKING

# ================================================================
#  Disable lazy loading for type checking
# ================================================================
if TYPE_CHECKING:
    # import classes
    from .model_settings_base import ModelSettingsBase
    from .field_variable import FieldVariable
    from .state_base import StateBase
    from .model_state import ModelState
    from .model import Model
    from .diagnose_imbalance_base import DiagnoseImbalanceBase
    from .mesh_point import MeshPoint


    # import modules
    from . import grid
    from . import domain_decomposition
    from . import config
    from . import utils
    from . import time_steppers
    from . import modules
    from . import projection
    from . import timing_module

    # import functions
    from .to_numpy import to_numpy

# ================================================================
#  Define all the possible imports
# ================================================================

# Set up dictionary that maps an import to a path
# items in the all_modules_by_origin dictionary are imported as modules
# items in the all_imports_by_origin dictionary are imported as elements of a module
all_modules_by_origin = {
    "fridom.framework": [
        "grid",
        "config",
        "utils",
        "time_steppers",
        "modules",
        "projection",
        "timing_module",
    ],
}

all_imports_by_origin = {
    "fridom.framework.model_settings_base": ["ModelSettingsBase"],
    "fridom.framework.field_variable": ["FieldVariable"],
    "fridom.framework.state_base": ["StateBase"],
    "fridom.framework.model_state": ["ModelState"],
    "fridom.framework.model": ["Model"],
    "fridom.framework.diagnose_imbalance_base": ["DiagnoseImbalanceBase"],
    "fridom.framework.mesh_point": ["MeshPoint"],
    "fridom.framework.to_numpy": ["to_numpy"],
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
