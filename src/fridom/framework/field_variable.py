# Import external modules
from typing import TYPE_CHECKING
from copy import deepcopy
from functools import partial
from mpi4py import MPI
import numpy as np
# Import internal modules
import fridom.framework as fr
from fridom.framework import config, utils
# Import type information
if TYPE_CHECKING:
    import xarray as xr
    from fridom.framework.model_settings_base import ModelSettingsBase
    from fridom.framework.grid.position import PositionBase
    from fridom.framework.grid.transform_type import TransformType



class FieldVariable:
    """
    Class for field variables in the framework.
    
    Description
    -----------
    TODO

    Parameters
    ----------
    `mset` : `ModelSettings`
        ModelSettings object
    `is_spectral` : `bool`
        True if the FieldVariable should be initialized in spectral space
    `name` : `str` 
        Name of the FieldVariable
    `topo` : `list[bool]` (default None)
        Topology of the FieldVariable. If None, the FieldVariable is
        assumed to be fully extended in all directions. If a list of booleans 
        is given, the FieldVariable has no extend in the directions where the
        corresponding entry is False.
    `transform_types` : `tuple[TransformType]` (default None)
        Tuple of TransformType objects that specify the type of transform
        that should be applied to nonperiodic axes (e.g. DST1, DST2, etc.).
        If None, the default transform type DCT2 is used.
    `arr` : `ndarray` (default None)
        The array to be wrapped
    
    Attributes
    ----------
    `name` : `str`
        The name of the FieldVariable
    `long_name` : `str`
        The long name of the FieldVariable
    `units` : `str`
        The unit of the FieldVariable
    `nc_attrs` : `dict`
        Dictionary with additional attributes for the NetCDF file
    `mset` : `ModelSettings`
        ModelSettings object
    `grid` : `Grid`
        Grid object
    `is_spectral` : `bool`
        True if the FieldVariable is in spectral space
    `topo` : `list[bool]`
        Topology of the FieldVariable
    `arr` : `ndarray`
        The underlying array
    
    Methods
    -------
    `fft()`
        Compute forward and backward Fourier transform of the FieldVariable
    `sync()`
        Synchronize the FieldVariable (exchange boundary values)
    `sqrt()`
        Compute the square root of the FieldVariable
    `norm_l2()`
        Compute the L2 norm of the FieldVariable
    
    """
    _dynamic_attributes = set(["arr", "position"])
    def __init__(self, 
                 mset: 'ModelSettingsBase',
                 name: str,
                 position: 'PositionBase',
                 transform_types: 'tuple[TransformType] | None' = None,
                 is_spectral=False, 
                 long_name="Unnamed", 
                 units="n/a",
                 nc_attrs=None,
                 topo=None,
                 arr=None,
                 flags: dict | list | None = None,
                 ) -> None:

        ncp = config.ncp
        dtype = config.dtype_comp if is_spectral else config.dtype_real
        topo = topo or [True] * mset.grid.n_dims
        if arr is None:
            # get the shape of the array
            if is_spectral:
                shape = tuple(n if p else 1 
                              for n, p in zip(mset.grid.K[0].shape, topo))
            else:
                shape = tuple(n if p else 1 
                              for n, p in zip(mset.grid.X[0].shape, topo))
            data = ncp.zeros(shape=shape, dtype=dtype)
        else:
            data = ncp.array(arr, dtype=dtype)

        # ----------------------------------------------------------------
        #  Set flags
        # ----------------------------------------------------------------
        self.flags = {"NO_ADV": False, 
                      "ENABLE_MIXING": False}
        if isinstance(flags, dict):
            self.flags.update(flags)
        elif isinstance(flags, list):
            for flag in flags:
                if flag not in self.flags:
                    config.logger.warning(f"Flag {flag} not available")
                    config.logger.warning(f"Available flags: {self.flags}")
                    raise ValueError
                self.flags[flag] = True

        # ----------------------------------------------------------------
        #  Set attributes
        # ----------------------------------------------------------------

        self.name = name
        self.position = position
        self.long_name = long_name
        self.transform_types = transform_types
        self.units = units
        self.nc_attrs = nc_attrs or {}
        self.mset = mset
        self.is_spectral = is_spectral
        self.topo = topo
        self.arr = data

        return
        
    # ==================================================================
    #  OTHER METHODS
    # ==================================================================

    def get_kw(self):
        """
        Return a dictionary with the keyword arguments for the
        FieldVariable constructor
        """
        return {"mset": self.mset, 
                "name": self.name,
                "position": self.position,
                "transform_types": self.transform_types,
                "long_name": self.long_name,
                "units": self.units,
                "nc_attrs": self.nc_attrs,
                "is_spectral": self.is_spectral, 
                "topo": self.topo,
                "flags": self.flags}

    def fft(self) -> "FieldVariable":
        """
        Compute forward and backward Fourier transform of the FieldVariable

        Returns:
            FieldVariable: Fourier transform of the FieldVariable
        """
        if not self.grid.fourier_transform_available:
            raise NotImplementedError(
                "Fourier transform not available for this grid")

        ncp = config.ncp
        if self.is_spectral:
            res = ncp.array(
                self.grid.ifft(self.arr, self.transform_types).real, 
                dtype=config.dtype_real)
        else:
            res = ncp.array(
                self.grid.fft(self.arr, self.transform_types),
                dtype=config.dtype_comp)
        from copy import copy
        f = copy(self)
        f.arr = res
        f.is_spectral = not self.is_spectral

        return f

    def sync(self) -> 'FieldVariable':
        """
        Synchronize the FieldVariable (exchange boundary values)
        """
        f = self
        f.arr = self.grid.sync(self.arr)
        return f

    def apply_boundary_conditions(self, 
                                  axis: int, 
                                  side: str, 
                                  value: 'float | np.ndarray | FieldVariable'
                                  ) -> 'FieldVariable':
        """
        Apply boundary conditions to the FieldVariable
        
        Parameters
        ----------
        `axis` : `int`
            Axis along which to apply the boundary condition
        `side` : `str`
            Side of the axis along which to apply the boundary condition
            (either "left" or "right")
        `value` : `float | np.ndarray | FieldVariable`
            The value of the boundary condition. If a float is provided, the
            boundary condition will be set to a constant value. If an array is
            provided, the boundary condition will be set to the array.
        
        Raises
        ------
        `NotImplementedError`
            If the FieldVariable is in spectral space
        """
        if self.is_spectral:
            raise NotImplementedError(
                "Boundary conditions not available in spectral space")
        f = self
        f.arr = self.grid.apply_boundary_condition(self.arr, axis, side, value)
        return f

    def norm_l2(self) -> float:
        """
        Compute the L2 norm of the FieldVariable

        Returns:
            float: L2 norm of the FieldVariable
        """
        return config.ncp.linalg.norm(self.arr)

    def has_nan(self) -> bool:
        """
        Check if the FieldVariable contains NaN values
        """
        return config.ncp.any(config.ncp.isnan(self.arr))

    # ==================================================================
    #  SLICING
    # ==================================================================

    def __getitem__(self, key):
        return self.arr[key]
    
    def __setitem__(self, key, value):
        new_arr = utils.modify_array(self.arr, key, value)
        self.arr = new_arr

    def __getattr__(self, name):
        """
        Forward attribute access to the underlying array (e.g. shape)
        """
        try:
            return getattr(self.arr, name)
        except AttributeError:
            raise AttributeError(f"FieldVariable has no attribute {name}")

    # For pickling
    def __getstate__(self):
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)

    def __deepcopy__(self, memo):
        return FieldVariable(arr=deepcopy(self.arr, memo), 
                             **deepcopy(self.get_kw(), memo))

    # ==================================================================
    #  ARITHMETIC OPERATIONS
    # ==================================================================
    def sum(self):
        """
        Global sum of the FieldVariable
        """
        ics = self.grid.inner_slice
        sum = self.arr[ics].sum()
        sum = MPI.COMM_WORLD.allreduce(sum, op=MPI.SUM)
        return sum

    def __sum__(self):
        return self.sum()

    def abs(self):
        """
        Absolute values of the FieldVariable
        """
        return FieldVariable(arr=config.ncp.abs(self.arr), **self.get_kw())

    def __abs__(self):
        return self.abs()
    
    def max(self):
        """
        Maximum value of the FieldVariable over the whole domain
        """
        ics = self.grid.inner_slice
        my_max = self.arr[ics].max()
        return MPI.COMM_WORLD.allreduce(my_max, op=MPI.MAX)

    def __max__(self):
        return self.max()
    
    def min(self):
        """
        Minimum value of the FieldVariable over the whole domain
        """
        ics = self.grid.inner_slice
        my_min = self.arr[ics].min()
        return MPI.COMM_WORLD.allreduce(my_min, op=MPI.MIN)
    
    def __min__(self):
        return self.min()

    def int(self):
        """
        Global integral of the FieldVariable
        """
        ics = self.grid.inner_slice
        integral = (self.arr * self.grid.dV)[ics].sum()
        return MPI.COMM_WORLD.allreduce(integral, op=MPI.SUM)


    def __add__(self, other):
        """
        Add A FieldVariable to another FieldVariable or a scalar

        # Arguments:
            other        : FieldVariable or array or scalar

        Returns:
            FieldVariable: Sum of self and other (inherits from self)
        """
        kwargs = self.get_kw()
        # Check that the other object is a FieldVariable
        if isinstance(other, FieldVariable):
            topo = [p or q for p, q in zip(self.topo, other.topo)]
            kwargs["topo"] = topo
            sum = self.arr + other.arr
        else:
            sum = self.arr + other

        return FieldVariable(arr=sum, **kwargs)
    
    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        """
        Subtract A FieldVariable to another FieldVariable or a scalar

        Arguments:
            other        : FieldVariable or array or scalar

        Returns:
            FieldVariable: Difference of self and other (inherits from self)
        """
        kwargs = self.get_kw()
        # Check that the other object is a FieldVariable
        if isinstance(other, FieldVariable):
            topo = [p or q for p, q in zip(self.topo, other.topo)]
            kwargs["topo"] = topo
            diff = self.arr - other.arr
        else:
            diff = self.arr - other

        return FieldVariable(arr=diff, **kwargs)
    
    def __rsub__(self, other):
        res = other - self.arr
        return FieldVariable(arr=res, **self.get_kw())

    def __mul__(self, other):
        """
        Multiply A FieldVariable to another FieldVariable or a scalar

        Arguments:
            other        : FieldVariable or array or scalar

        Returns:
            FieldVariable: Product of self and other (inherits from self)
        """
        kwargs = self.get_kw()
        # Check that the other object is a FieldVariable
        if isinstance(other, FieldVariable):
            topo = [p or q for p, q in zip(self.topo, other.topo)]
            kwargs["topo"] = topo
            prod = self.arr * other.arr
        else:
            prod = self.arr * other

        return FieldVariable(arr=prod, **kwargs)
    
    def __rmul__(self, other):
        return self.__mul__(other)
    
    def __truediv__(self, other):
        """
        Divide A FieldVariable to another FieldVariable or a scalar

        Arguments:
            other        : FieldVariable or array or scalar

        Returns:
            FieldVariable: Quotient of self and other (inherits from self)
        """
        kwargs = self.get_kw()
        # Check that the other object is a FieldVariable
        if isinstance(other, FieldVariable):
            topo = [p or q for p, q in zip(self.topo, other.topo)]
            kwargs["topo"] = topo
            quot = self.arr / other.arr
        else:
            quot = self.arr / other

        return FieldVariable(arr=quot, **kwargs)
    
    def __rtruediv__(self, other):
        return FieldVariable(arr=other / self.arr, **self.get_kw())

    def __pow__(self, other):
        """
        Raise A FieldVariable to another FieldVariable or a scalar

        Arguments:
            other        : FieldVariable or array or scalar

        Returns:
            FieldVariable: Power of self and other (inherits from self)
        """
        kwargs = self.get_kw()
        # Check that the other object is a FieldVariable
        if isinstance(other, FieldVariable):
            topo = [p or q for p, q in zip(self.topo, other.topo)]
            kwargs["topo"] = topo
            pow = self.arr ** other.arr
        else:
            pow = self.arr ** other

        return FieldVariable(arr=pow, **kwargs)

    # ==================================================================
    #  STRING REPRESENTATION
    # ==================================================================

    def __str__(self) -> str:
        return f"FieldVariable: {self.name} \n {self.arr}"

    def __repr__(self) -> str:
        return self.__str__()

    # ================================================================
    #  xarray conversion
    # ================================================================
    @property
    def xr(self) -> 'xr.DataArray':
        """
        Conversion to xarray DataArray
        """
        return self.xrs[:]

    @property
    def xrs(self):
        """
        Conversion to xarray DataArray for a selected slice
        """
        def slicer(key):
            import xarray as xr
            fv = self
            # convert key to tuple
            ndim = fv.grid.n_dims
            if not isinstance(key, (tuple, list)):
                key = [key]
            else:
                key = list(key)
            key += [slice(None)] * (ndim - len(key))

            # get the inner of the field
            if fv.is_spectral:
                # no inner slice for spectral fields
                ics = [slice(None)] * ndim
            else:
                ics = list(fv.grid.inner_slice)

            for i in range(ndim):
                # set non-extended axes to 0
                if not fv.topo[i]:
                    ics[i] = slice(0,1)
                    key[i] = slice(0,1)
                if isinstance(key[i], int):
                    key[i] = slice(key[i], key[i]+1)

            arr = fr.utils.to_numpy(fv.arr[tuple(ics)][tuple(key)])

            # get the coordinates
            if ndim <= 3:
                if fv.is_spectral:
                    all_dims = tuple(["kx", "ky", "kz"][:ndim])
                else:
                    all_dims = tuple(["x", "y", "z"][:ndim])
            else:
                if fv.is_spectral:
                    all_dims = tuple(f"k{i}" for i in range(ndim))
                else:
                    all_dims = tuple(f"x{i}" for i in range(ndim))

            dims = []
            coords = {}
            for axis in range(fv.grid.n_dims):
                if arr.shape[axis] == 1:
                    # skip non-extended axes
                    continue

                dim = all_dims[axis]
                dims.append(dim)
                if fv.is_spectral:
                    x_sel = fv.grid.k_local[axis][key[axis]]
                else:
                    x_sel = fv.grid.x_local[axis][key[axis]]
                coords[dim] = fr.utils.to_numpy(x_sel)

            # reverse the dimensions
            dims = dims[::-1]
    
            dv = xr.DataArray(
                np.squeeze(arr).T, 
                coords=coords, 
                dims=tuple(dims),
                name=fv.name,
                attrs={"long_name": fv.long_name, "units": fv.units})
    
            if fv.is_spectral:
                x_unit = "1/m"
            else:
                x_unit = "m"
            for dim in dims:
                dv[dim].attrs["units"] = x_unit
            return dv
        return fr.utils.SliceableAttribute(slicer)


    # ================================================================
    #  Properties
    # ================================================================
    @property
    def grid(self):
        """Return the grid of the FieldVariable"""
        return self.mset.grid


utils.jaxify_class(FieldVariable)