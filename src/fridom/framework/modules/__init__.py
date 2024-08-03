"""
Base classes and functions for creating modules in the model.
"""
from lazypimp import setup
from typing import TYPE_CHECKING

# ================================================================
#  Disable lazy loading for type checking
# ================================================================
if TYPE_CHECKING:
    # importing modules
    from . import animation

    # importing the Classes
    from .module import Module
    from .module_container import ModuleContainer
    from .restart_module import RestartModule
    from .boundary_conditions import BoundaryConditions
    from .netcdf_writer_single_proc import NetCDFWriterSingleProc
    from .netcdf_writer import NetCDFWriter
    from .reset_tendency import ResetTendency

    # importing the functions
    from .module import setup_module, module_method
    
# ================================================================
#  Setup lazy loading
# ================================================================
base_path = "fridom.framework.modules"

all_modules_by_origin = { base_path: ["animation"] }

all_imports_by_origin = { 
    f"{base_path}.module": ["Module", "setup_module", "module_method"],
    f"{base_path}.module_container": ["ModuleContainer"],
    f"{base_path}.restart_module": ["RestartModule"],
    f"{base_path}.boundary_conditions": ["BoundaryConditions"],
    f"{base_path}.netcdf_writer_single_proc": ["NetCDFWriterSingleProc"],
    f"{base_path}.netcdf_writer": ["NetCDFWriter"],
    f"{base_path}.reset_tendency": ["ResetTendency"],
}

setup(__name__, all_modules_by_origin, all_imports_by_origin)