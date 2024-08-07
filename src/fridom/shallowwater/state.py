from fridom.shallowwater.model_settings import ModelSettings
from fridom.shallowwater.grid import Grid
from fridom.framework.field_variable import FieldVariable
from fridom.framework.state_base import StateBase


class State(StateBase):
    def __init__(self, 
                 grid: Grid, 
                 is_spectral=False, 
                 field_list=None) -> None:
        if field_list is None:
            from fridom.framework.field_variable import FieldVariable
            u = FieldVariable(grid,
                name="Velocity u", is_spectral=is_spectral)
            v = FieldVariable(grid,
                name="Velocity v", is_spectral=is_spectral)
            h = FieldVariable(grid,
                name="Layer Thickness h", is_spectral=is_spectral)
            field_list = [u, v, h]
        super().__init__(grid, field_list, is_spectral)
        self.mset = grid.mset
        self.constructor = State
        return
    
    # ======================================================================
    #  ENERGY
    # ======================================================================

    def ekin(self) -> FieldVariable:
        """
        Calculate the kinetic energy field.
        $ ekin = 0.5 * Ro * h_full * (u^2 + v^2) $
        $ h_full = c^2 + Ro * h $

        Returns:
            ekin (FieldVariable)  : Kinetic energy field.
        """
        # First transform to physical space if necessary
        z = self
        if self.is_spectral:
            z = self.fft()

        csqr = self.mset.csqr; Ro = self.mset.Ro
        h_full = csqr + Ro * self.h
        ekin = 0.5 * Ro**2 * h_full * (z.u**2 + z.v**2)
        from fridom.framework.field_variable import FieldVariable
        return FieldVariable(self.grid, is_spectral=False, 
                             name="Kinetic Energy", arr=ekin)

    def epot(self) -> FieldVariable:
        """
        Calculate the potential energy field.
        $ epot = 0.5 * h_full * h $
        $ h_full = c^2 + Ro * h $

        Returns:
            epot (FieldVariable)  : Potential energy field.
        """
        # First transform to physical space if necessary
        z = self
        if self.is_spectral:
            z = self.fft()

        csqr = self.mset.csqr; Ro = self.mset.Ro
        h_full = csqr + Ro * z.h
        epot = 0.5 * h_full ** 2

        from fridom.framework.field_variable import FieldVariable
        return FieldVariable(self.grid, is_spectral=False,
                             name="Potential Energy", arr=epot)
    
    def etot(self) -> FieldVariable:
        """
        Calculate the total energy field.
        $ etot = ekin + epot $

        Returns:
            etot (FieldVariable)  : Total energy field.
        """
        etot = (self.ekin() + self.epot()).arr
        from fridom.framework.field_variable import FieldVariable
        return FieldVariable(self.grid, is_spectral=False,
                             name="Total Energy", arr=etot)

    def mean_ekin(self) -> float:
        """
        Calculate the mean kinetic energy.

        Returns:
            mean_ekin (float)  : Mean kinetic energy.
        """
        return self.cp.mean(self.ekin())
    
    def mean_epot(self) -> float:
        """
        Calculate the mean potential energy.

        Returns:
            mean_epot (float)  : Mean potential energy.
        """
        return self.cp.mean(self.epot())
    
    def mean_etot(self) -> float:
        """
        Calculate the mean total energy.

        Returns:
            mean_etot (float)  : Mean total energy.
        """
        return self.cp.mean(self.etot())

    # ======================================================================
    #  VORTICITY
    # ======================================================================

    def hor_vort(self) -> FieldVariable:
        """
        Calculate the horizontal vorticity field.
        $ hor_vort = \partial_x v - \partial_y u $

        Returns:
            hor_vort (FieldVariable)  : Horizontal vorticity field.
        """
        # shortcuts
        u  = self.u
        v  = self.v

        # calculate the horizontal vorticity
        vort = ((v.diff_forward(0) -  u.diff_forward(1))
                ).ave(-1, 0).ave(-1, 1)

        # Create the field variable
        from fridom.framework.field_variable import FieldVariable
        field = FieldVariable(self.grid, is_spectral=False, 
                              name="Horizontal Vorticity", arr=vort)
        return field

    def pot_vort(self) -> FieldVariable:
        """
        Calculate the potential vorticity field.
        q = (Zeta + f0) / (c² + Ro*h)

        Returns:
            pot_vort (FieldVariable)  : Scaled potential vorticity field.
        """

        # shortcuts
        f0 = self.mset.f0; 
        Ro = self.mset.Ro; csqr = self.mset.csqr

        rel_vort = self.hor_vort()
        h_full = csqr + Ro * self.h
        pot_vort = (rel_vort + f0) / h_full

        # Create the field variable
        from fridom.framework.field_variable import FieldVariable
        field = FieldVariable(self.grid, arr=pot_vort,
                              is_spectral=False, name="Potential Vorticity")
        return field

    # ======================================================================
    #  SOME MATH FUNCTIONS
    # ======================================================================

    def rot90(self):
        """
        Rotate the state by 90 degrees. (mathematically positive direction)
        """
        z_phy = self.fft() if self.is_spectral else self
        z_rot = State(self.mset, self.grid, is_spectral=False)
        z_rot.h[:] = self.cp.rot90(z_phy.h)
        z_rot.u[:-1,:] = -self.cp.rot90(z_phy.v[:,:-1])
        if self.mset.periodic_bounds[1]:
            z_rot.u[-1,:] = -z_phy.v[:,-1]
        z_rot.v[:] = self.cp.rot90(z_phy.u)
        return z_rot.fft() if self.is_spectral else z_rot

    def rot180(self):
        """
        Rotate the state by 180 degrees. (mathematically positive direction)
        """
        rot90 = self.cp.rot90
        z_phy = self.fft() if self.is_spectral else self
        z_rot = State(self.mset, self.grid, is_spectral=False)
        z_rot.h[:] = rot90(rot90(z_phy.h))
        z_rot.u[:-1,:] = -rot90(rot90(z_phy.u[:-1,:]))
        z_rot.v[:,:-1] = -rot90(rot90(z_phy.v[:,:-1]))
        return z_rot.fft() if self.is_spectral else z_rot


    # ======================================================================
    #  CFL AND PECLET NUMBERS
    # ======================================================================

    def max_cfl(self) -> float:
        """
        Calculate the maximum horizontal CFL number.

        Returns:
            max_cfl (float)  : Maximum horizontal CFL number.
        """
        u = self.u; v = self.v
        sqrt = self.cp.sqrt; maxi = self.cp.max
        dx = min(self.mset.dx, self.mset.dy)
        return sqrt(maxi(u**2 + v**2)) * self.mset.dt / dx

    def pecl(self) -> float:
        """
        Calculate the horizontal Peclet number.

        Returns:
            pecl (float)  : Horizontal Peclet number.
        """
        umax = self.cp.max(self.u**2 + self.v**2)
        res = min(umax*self.mset.dx/(1e-32 + self.mset.ah),
                  umax*self.mset.dx**3/(1e-32 + self.mset.ahbi))
        return res

    @property
    def u(self) -> FieldVariable:
        return self.field_list[0]
    
    @u.setter
    def u(self, value: FieldVariable):
        self.field_list[0] = value
        return
    
    @property
    def v(self) -> FieldVariable:
        return self.field_list[1]
    
    @v.setter
    def v(self, value: FieldVariable):
        self.field_list[1] = value
        return
    
    @property
    def h(self) -> FieldVariable:
        return self.field_list[2]

    @h.setter
    def h(self, value: FieldVariable):
        self.field_list[2] = value
        return
    
# remove symbols from namespace
del ModelSettings, Grid, FieldVariable, StateBase