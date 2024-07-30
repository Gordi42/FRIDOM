import fridom.nonhydro as nh

class WavePackage(nh.State):
    """
    Wave package initial condition.
    
    Description
    -----------
    Creates a polarized single wave (`nh.initial_conditions.SingleWave`) and 
    applies a mask to it. The mask is a Gaussian function centered at 
    `mask_pos` with a width of `mask_width`:

    .. math::
        M(x) = \\prod_{i=1}^{3} \\exp\\left(\\frac{(x_i - p_i)^2}{w_i^2}\\right)
    
    where :math:`p_i` is the position and :math:`w_i` is the width of the mask
    in the :math:`i`-th direction. The final wave package is given by:

    .. math::
        z = \\mathbf{P}_s \cdot \\left( S(x) M(x) \\right)
    
    where :math:`S(x)` is the single wave and :math:`\\mathbf{P}_s` is the
    projection operator onto the mode `s`.
    
    Parameters
    ----------
    `mset` : `ModelSettings`
        The model settings.
    `mask_pos` : `tuple[float | None]`
        The position of the mask in the x, y, and z directions.
        If `None`, the mask is not applied in that direction.
    `mask_width` : `tuple[float | None]`
        The width of the mask in the x, y, and z directions.
        If `None`, the mask is not applied in that direction.
    `kx` : `int`
        The wavenumber in the x-direction.
    `ky` : `int`
        The wavenumber in the y-direction.
    `kz` : `int`
        The wavenumber in the z-direction.
    `s` : `int`
        The mode (0, 1, -1)
        0 => geostrophic mode
        1 => positive inertia-gravity mode
         -1 => negative inertia-gravity mode
    `phase` : `real`
        The phase of the wave. (Default: 0)
    
    Attributes
    ----------
    `omega` : `complex`
        The frequency of the wave (only for inertia-gravity modes).
    `period` : `float`
        The period of the wave (only for inertia-gravity modes).
    
    Examples
    --------
    >>> import fridom.nonhydro as nh
    >>> import numpy as np
    >>> grid = nh.grid.cartesian.Grid(
    ...     N=(256, 2, 256), L=(1, 1, 1), periodic_bounds=(True, True, True))
    >>> mset = nh.ModelSettings(grid=grid, f0=1, N2=1, dsqr=0.01, Ro=0.0)
    >>> mset.time_stepper.dt = np.timedelta64(10, 'ms')
    >>> mset.setup()
    >>> z = nh.initial_conditions.WavePackage(
    ...     mset, mask_pos=(0.5, None, 0.5), mask_width=(0.1, None, 0.1), 
    ...     kx=20, ky=0, kz=20)
    >>> model = nh.Model(mset)
    >>> model.z = z
    >>> model.run(runlen=np.timedelta64(20, 's'))
    """
    def __init__(self, 
                 mset: nh.ModelSettings, 
                 mask_pos: tuple[float | None],
                 mask_width: tuple[float | None],
                 kx: int = 0, 
                 ky: int = 0, 
                 kz: int = 0, 
                 s: int = 1, 
                 phase: float = 0, 
                 ) -> None:
        super().__init__(mset)

        # Shortcuts
        ncp = nh.config.ncp
        grid = mset.grid

        # Construct single wave
        ic = nh.initial_conditions
        z = ic.SingleWave(mset, kx, ky, kz, s, phase)

        if s != 0:
            self.omega = z.omega
            self.period = z.period

        # Construct mask
        mask = ncp.ones_like(grid.X[0])
        for x, pos, width in zip(grid.X, mask_pos, mask_width):
            if pos is not None and width is not None:
                mask *= ncp.exp(-(x - pos)**2 / width**2)

        # Apply mask
        z *= mask

        # Project onto the mode again
        q = nh.eigenvectors.VecQ(s, mset)
        p = nh.eigenvectors.VecP(s, mset)
        z = z.project(p, q)

        # Inertia-gravity modes have to be multiplied by 2
        if s != 0:
            z *= 2

        # save the state
        self.fields = z.fields
        return