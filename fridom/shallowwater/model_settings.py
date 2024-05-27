import numpy as np

from fridom.framework.modelsettings_base import ModelSettingsBase

class ModelSettings(ModelSettingsBase):
    """
    Settings container for the model.

    Attributes:
        dtype (np.dtype)       : Data type for real.         
        ctype (np.dtype)       : Data type for complex.       
        gpu (bool)             : Switch for GPU.              
        csqr (dtype)           : Square of phase speed (Burger number).
        f0 (dtype)             : Coriolis parameter.         
        beta (dtype)           : Beta term for Coriolis parameter.
        Ro (dtype)             : Rossby number.                
        L (list)               : Domain size in each direction.
        N (list)               : Grid points in each direction.
        dx (dtype)             : Grid spacing in x-direction.
        dy (dtype)             : Grid spacing in y-direction.
        dz (dtype)             : Grid spacing in z-direction.
        periodic_bounds (list) : List of bools for periodic boundaries.
        dt (dtype)             : Time step size.
        eps (dtype)            : 2nd order bashforth correction.
        AB1 (np.ndarray)       : 1st order Adams-Bashforth coefficients.
        AB2 (np.ndarray)       : 2nd order Adams-Bashforth coefficients.
        AB3 (np.ndarray)       : 3rd order Adams-Bashforth coefficients.
        AB4 (np.ndarray)       : 4th order Adams-Bashforth coefficients.

        solver (str)           : Solver name ("Spectral", "FD").

        enable_nonlinear (bool) : Enable nonlinear terms.
        enable_varying_f (bool) : Enable varying Coriolis parameter.
        enable_source (bool)    : Enable source terms.
        enable_biharmonic (bool): Enable biharmonic friction and mixing.
        enable_harmonic (bool)  : Enable harmonic friction and mixing.
        enable_tqdm (bool)      : Enable progress bar.
        enable_diag (bool)      : Enable diagnostic output.
        enable_verbose (bool)   : Enable verbose output.
    """
    def __init__(self, dtype=np.float64, ctype=np.complex128, **kwargs):
        """
        Constructor.

        Args:
            dtype (np.dtype)   : Data type for real.         
            ctype (np.dtype)   : Data type for complex.
        """
        super().__init__(n_dims=2, dtype=dtype, ctype=ctype)
        self.model_name = "ShallowWater"
        self.L = [2*np.pi, 2*np.pi]
        self.N = [63, 63]

        # physical parameters
        self.csqr = dtype(1)
        self.f0   = dtype(1)
        self.beta = dtype(0)
        self.Ro   = dtype(0.1)

        # main tendency
        from fridom.shallowwater.modules.main_tendency import MainTendency
        self.tendencies = MainTendency()

        # state constructor
        from fridom.shallowwater.state import State
        self.state_constructor = lambda grid: State(grid, is_spectral=False)

        # model state constructor
        from fridom.shallowwater.model_state import ModelState
        self.model_state_constructor = lambda grid: ModelState(grid)

        # ------------------------------------------------------------------
        #   SWITCHES
        
        # Physics
        self.enable_varying_f  = False   # Enable varying Coriolis parameter

        # Set attributes from keyword arguments
        for key, value in kwargs.items():
            # Check if attribute exists
            if not hasattr(self, key):
                raise AttributeError(
                    "ModelSettings has no attribute '{}'".format(key)
                    )
            setattr(self, key, value)

    def __str__(self) -> str:
        """
        String representation of the model settings.

        Returns:
            res (str): String representation of the model settings.
        """
        res = super().__str__()
        res += "  Physical parameters:\n"
        res += "    csqr = {:.3f}\n".format(self.csqr)
        res += "    f0   = {:.3f}\n".format(self.f0)
        res += "    beta = {:.3f}\n".format(self.beta)
        res += "    Ro   = {:.3f}\n".format(self.Ro)
        res += "  Switches:\n"
        res += "    enable_varying_f  = {}\n".format(self.enable_varying_f)
        res += "================================================\n"
        return res

    def __repr__(self) -> str:
        """
        String representation of the model settings (for IPython).

        Returns:
            res (str): String representation of the model settings.
        """
        return self.__str__()


    # ==================================================================
    #  GETTER AND SETTER FOR PRIVATE VARIABLES
    # ==================================================================
    @property
    def N(self) -> list:
        """Grid points in each direction."""
        return self._N
    
    @N.setter
    def N(self, value: list):
        self._N = [int(val) for val in value]
        self._dg = [L / N for L, N in zip(self._L, self._N)]
        self._total_grid_points = 1
        for n in self._N:
            self._total_grid_points *= n
        self.max_cg_iter = max(self._N)
    
    @property
    def dx(self) -> float:
        """Grid spacing in x-direction."""
        return self.dg[0]
    
    @property
    def dy(self) -> float:
        """Grid spacing in y-direction."""
        return self.dg[1]

# remove symbols from namespace
del ModelSettingsBase