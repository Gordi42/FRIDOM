from fridom.NonHydrostatic.ModelSettings import ModelSettings
from fridom.NonHydrostatic.Grid import Grid
from fridom.NonHydrostatic.State import State
from fridom.NonHydrostatic.BoundaryConditions import PBoundary
from fridom.NonHydrostatic.Modules import *
from fridom.Framework.FieldVariable import FieldVariable
from fridom.Framework.ModelBase import ModelBase


class Model(ModelBase):
    """
    A 3D non-hydrostatic Boussinesq model. Based on the ps3D model by
    Prof. Carsten Eden ( https://github.com/ceden/ps3D ).

    Attributes:
        z (State)               : State variables (u,v,w,b).
        p (FieldVariable)       : Pressure (p).
        it (int)                : Iteration counter.
        timer (TimingModule)    : Timer.
        writer (NetCDFWriter)   : NetCDF writer.
        Modules:                : Modules of the model.

    Methods:
        step()                  : Perform one time step.
        run()                   : Run the model for a given number of steps.
        reset()                 : Reset the model (pointers, tendencies)
        diagnose()              : Print diagnostic information.
        update_pointer()        : Update pointer for Adam-Bashforth time stepping.
        update_coeff_AB()       : Update coeffs for Adam-Bashforth time stepping.
        adam_bashforth()        : Perform Adam-Bashforth time stepping.
    """

    def __init__(self, mset:ModelSettings, grid:Grid) -> None:
        """
        Constructor.

        Args:
            mset (ModelSettings)    : Model settings.
            grid (Grid)             : Grid.
        """
        super().__init__(mset, grid, State)
        self.mset = mset

        # Add pressure and divergence variables
        self.p = FieldVariable(mset, grid, 
                    name="Pressure p", bc=PBoundary(mset))
        self.div = FieldVariable(mset, grid,
                    name="Divergence", bc=PBoundary(mset))
        
        # Modules
        self.linear_tendency     = LinearTendency(mset, grid, self.timer)
        self.nonlinear_tendency  = NonlinearTendency(mset, grid, self.timer)
        self.pressure_gradient   = PressureGradientTendency(mset, grid, self.timer)
        self.pressure_solver     = PressureSolve(mset, grid, self.timer)
        self.harmonic_friction   = HarmonicFriction(mset, grid, self.timer)
        self.harmonic_mixing     = HarmonicMixing(mset, grid, self.timer)
        self.biharmonic_friction = BiharmonicFriction(mset, grid, self.timer)
        self.biharmonic_mixing   = BiharmonicMixing(mset, grid, self.timer)
        self.source_tendency     = SourceTendency(mset, grid, self.timer)


        # netcdf writer
        var_names = ["u", "v", "w", "b", "p"]
        var_long_names = ["Velocity u", "Velocity v", "Velocity w", 
                            "Buoyancy b", "Pressure p"]
        var_unit_names = ["m/s", "m/s", "m/s", "m/s^2", "m^2/s^2"]
        self.writer.set_var_names(var_names, var_long_names, var_unit_names)

        return

    # ============================================================
    #   TOTAL TENDENCY
    # ============================================================

    def total_tendency(self):
        
        # calculate linear tendency
        self.linear_tendency(self.z, self.dz)

        # calculate nonlinear tendency
        if self.mset.enable_nonlinear:
            self.nonlinear_tendency(self.z, self.dz)

        # Friction And Mixing
        if self.mset.enable_harmonic:
            self.harmonic_friction(self.z, self.dz)
            self.harmonic_mixing(self.z, self.dz)

        if self.mset.enable_biharmonic:
            self.biharmonic_friction(self.z, self.dz)
            self.biharmonic_mixing(self.z, self.dz)

        if self.mset.enable_source:
            self.source_tendency(self.dz, self.time)

        # solve for pressure
        self.pressure_solver(self.dz, self.p)
        self.pressure_gradient(self.p, self.dz)

        return



    # ============================================================
    #   OTHER METHODS
    # ============================================================

    def reset(self) -> None:
        """
        Reset the model (pointers, tendencies).
        """
        super().reset()
        self.p = self.p*0
        return


    def diagnostics(self) -> None:
        """
        Print diagnostic information.
        """
        out = "Diagnostic at t = {:.2f}\n".format(self.it * self.mset.dt)
        out += "MKE = {:.2e},    ".format(self.z.mean_ekin())
        out += "MPE = {:.2e},    ".format(self.z.mean_epot())
        out += "MTE = {:.2e}\n".format(self.z.mean_etot())
        out += "hor. CFL = {:.2f},           ".format(self.z.max_cfl_h())
        out += "vert. CFL = {:.2f}".format(self.z.max_cfl_v())
        print(out)
        return

    def get_writer_variables(self):
        return [self.z.u, self.z.v, self.z.w, self.z.b, self.p]

    def update_live_animation(self):
        self.live_animation.update(z=self.z, p=self.p, time=self.time)
        return
    
    def update_vid_animation(self):
        self.vid_animation.update(z=self.z.cpu(), p=self.p.cpu(), time=self.time)
