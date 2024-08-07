"""
A 2D shallow water model

Description
-----------
A scaled rotating shallow water model. The discretization is based on a
energy conserving finite difference scheme on a staggered Arakawa C-grid.
Based on Sadourny [1975].

## Example:
Examples
--------
TODO: Update this example (it is not working)

.. code-block:: python

    import fridom.shallowwater as sw
    mset = sw.ModelSettings()                  # create model settings
    mset.N = [2**7, 2**7]                      # set resolution
    mset.L = [4, 4]                            # set domain size
    grid = sw.Grid(mset)                       # create grid
    model = sw.Model(grid)                     # create model
    model.z = sw.initial_conditions.Jet(grid)  # set initial conditions
    model.run(runlen=2)                        # run model

    # plot top view of final kinetic energy
    sw.Plot(model.z.ekin())(model.z)
"""

# import all the classes and functions from the nonhydro module
from .model_settings import ModelSettings
from .grid import Grid
from .state import State
from .plot import Plot, PlotContainer
from .model_plotter import ModelPlotter
from .diagnosed_imbalance import DiagnoseImbalance

# move classes from the framework into the shallowwater namespace
from fridom.framework.field_variable import FieldVariable
from fridom.framework.model_state import ModelState
from fridom.framework.model import Model

# import modules
from . import modules
from . import initial_conditions
from . import projection
from . import eigenvectors

# move the time steppers into the shallowwater namespace
from fridom.framework import time_steppers