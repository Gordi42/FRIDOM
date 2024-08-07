"""
A 3D non-hydrostatic Boussinesq model.

Description
-----------
The model is based on the ps3D model by Prof. Carsten Eden 
( https://github.com/ceden/ps3D ).

Examples
--------
TODO: Update this example (it is not working)
>>> # Provide examples of how to use this module.
>>> import fridom.nonhydro as nh
>>> mset = nh.ModelSettings()                  # create model settings
>>> mset.N = (2**7, 2**7, 2**4)                # set resolution
>>> mset.L = [4, 4, 1]                         # set domain size 
>>> grid = nh.Grid(mset)                       # create grid
>>> model = nh.Model(grid)                     # create model
>>> model.z = nh.initial_conditions.Jet(grid)  # set initial conditions
>>> model.run(runlen=2)                        # run model
>>> 
>>> # plot top view of final kinetic energy
>>> nh.Plot(model.z.ekin()).top(model.z)
"""
from lazypimp import setup
from typing import TYPE_CHECKING

# ================================================================
#  Disable lazy loading for type checking
# ================================================================
if TYPE_CHECKING:
    # ----------------------------------------------------------------
    #  Importing model specific classes and modules
    # ----------------------------------------------------------------
    # importing modules
    from . import grid
    from . import modules
    from . import initial_conditions

    # importing classes
    from .model_settings import ModelSettings
    from .state import State, DiagnosticState

    # ----------------------------------------------------------------
    #  Importing generic classes and modules
    # ----------------------------------------------------------------
    # importing modules
    from fridom.framework import config
    from fridom.framework import utils
    from fridom.framework import time_steppers
    from fridom.framework import projection

    # importing classes
    from fridom.framework.field_variable import FieldVariable
    from fridom.framework.model_state import ModelState
    from fridom.framework.model import Model
    
# ================================================================
#  Setup lazy loading
# ================================================================
all_modules_by_origin = { 
    "fridom.nonhydro": ["grid", "modules", "initial_conditions"],
    "fridom.framework": ["config", "time_steppers", "utils", "projection"],
}

all_imports_by_origin = { 
    "fridom.nonhydro.model_settings": ["ModelSettings"],
    "fridom.nonhydro.state": ["State", "DiagnosticState"],
    "fridom.framework.field_variable": ["FieldVariable"],
    "fridom.framework.model_state": ["ModelState"],
    "fridom.framework.model": ["Model"],
}

setup(__name__, all_modules_by_origin, all_imports_by_origin)
