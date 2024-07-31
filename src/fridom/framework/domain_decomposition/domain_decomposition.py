# Import external modules
from mpi4py import MPI
from copy import deepcopy
import numpy as np
from functools import partial
# Import internal modules
from .subdomain import Subdomain
from fridom.framework import config, utils

def _make_slice_tuple(s: slice, n_dims: int):
    """
    Create a tuple of slices for halo exchange.
        
    Description
    -----------
    Lets assume we want to access the halo region that is shared with the
    previous processor. For a 2D domain, two such regions exist, one in the
    x-direction and one in the y-direction. Hence we need to create two
    slices, one for each dimension. In this example and a halo of 2, the
    slices would be (slice(0, 2), slice(None)) and 
    (slice(None), slice(0, 2)). This function for s=slice(0, 2) would
    return the tuple of the two slice-tuples.
        
    Parameters
    ----------
    `s` : `slice`
        A 1D slice that defines the halo region in one dimension.
    `n_dims` : `int`
        The number of dimensions.
        
    Returns
    -------
    `tuple[tuple[slice]]`
        A list of slice tuples for each dimension.
        
    Examples
    --------
    >>> halo = 2
    >>> n_dims = 2
    >>> send_to_next = _make_slice_tuple(slice(-2*halo, -halo))
    >>> send_to_next
    >>> # ((slice(-4, -2), slice(None)), (slice(None), slice(-4, -2)))
    >>> # send_to_next[0] is used to send data to the next processor in the
    >>> # first dimension, send_to_next[1] is used to send data to the next
    >>> # processor in the second dimension
    """
    slice_list = []
    for i in range(n_dims):
        full_slice = [slice(None)]*n_dims
        full_slice[i] = s
        slice_list.append(tuple(full_slice))
    return tuple(slice_list)

def set_device():
    """
    Sync the gpu device with the processor rank. This function should be
    called once at the beginning of the simulation.
        
    Description
    -----------
    Let's assume we have a node with 4 GPUs and start a program with 4
    processors. By default, each processor will uses the first GPU. This
    function ensures that each processor uses a different GPU.
        
    Parameters
    ----------
    `backend_is_cupy` : `bool`
        Whether the backend is cupy or not.
    """
    if config.backend == "cupy":
        cp = config.ncp
        comm_node = MPI.COMM_WORLD.Split_type(MPI.COMM_TYPE_SHARED)
        node_rank = comm_node.Get_rank()
        num_gpus = cp.cuda.runtime.getDeviceCount()
        device_id = node_rank % num_gpus
        cp.cuda.Device(device_id).use()
        comm_node.Free()
    return



class DomainDecomposition:
    """
    Construct a grid of processors and decompose a global domain into subdomains.
    
    Description
    -----------
    Decompose the global domain into subdomains for parallel computing. The
    domain decomposition is done in a cartesian grid of processors. The
    decomposition can be done in multiple dimensions. Axes that are shared
    between processors can be specified (e.g. for fft)

    ::

                   ----------------------------------- 
                  /                /                /| 
                 /                /                / | 
                /                /                /  | 
               /                /                /   | 
              /                /                /    | 
             /                /                /    /| 
            /                /                /    / | 
            ----------------------------------    /  | 
           |                |                |   /   | 
           |   PROCESSOR    |   PROCESSOR    |  /    | 
           |     0, 1       |     1, 1       | /    /
           |                |                |/    /
           |----------------|----------------|    /     ^
           |                |                |   /     /
           |   PROCESSOR    |   PROCESSOR    |  /     / shared_axis
           |     0, 0       |     1, 0       | /     /
           |                |                |/
           ----------------------------------- 

    Parameters
    ----------
    `n_global` : `tuple[int]`
        The total number of grid points in each dimension.
    `halo` : `int`, optional (default=0)
        The number of halo cells (ghost cells) around the local domain
        for the exchange of boundary values.
    `shared_axes` : `list[int]`, optional (default=None)
        A list of axes that are shared between processors.
    `reorder_comm` : `bool`, optional (default=True)
        Whether to reorder the communicator.
    
    Examples
    --------
    .. code-block:: python

        from fridom.framework import config
        from fridom.framework.domain_decomposition import DomainDecomposition
        # create a domain decomposition that shares the x-axis
        dom = DomainDecomposition(
            n_global=(128, 128), halo=2, shared_axes=[0])
        
        # create a random array on the local domain
        u = config.ncp.random.rand(*dom_x.my_subdomain.shape)
        
        # synchronize the halo regions between neighboring domains
        dom_x.sync(u)
    """
    _dynamic_attributes = []
    def __init__(self, 
                 n_global: 'tuple[int]', 
                 halo: int = 0,
                 shared_axes: 'list[int] | None' = None,
                 reorder_comm = True,
                 ) -> None:
        # set input parameters
        n_dims = len(n_global)

        # set the device (only important for cupy backend)
        set_device()

        # --------------------------------------------------------------
        #  Get the number of processors in each direction
        # --------------------------------------------------------------
        # set the number of processors to 1 for shared axes
        shared_axes = shared_axes or []
        n_procs = []
        for i in range(n_dims):
            if i in shared_axes:
                n_procs.append(1)
            elif n_global[i] == 1:
                n_procs.append(1)
            else:
                n_procs.append(0)
        # calculate the remaining dimensions that are not shared
        n_procs = MPI.Compute_dims(MPI.COMM_WORLD.Get_size(), n_procs)
        # update the shared axes
        shared_axes = [i for i, n in enumerate(n_procs) if n == 1]

        # --------------------------------------------------------------
        #  Initialize the communicators
        # --------------------------------------------------------------
        comm = MPI.COMM_WORLD.Create_cart(
            n_procs, periods=[True]*n_dims, reorder=reorder_comm)
        size = comm.Get_size()
        rank = comm.Get_rank()

        # --------------------------------------------------------------
        #  Create subdomains
        # --------------------------------------------------------------
        all_subdomains = [Subdomain(i, comm, n_global, halo) for i in range(size)]
        my_subdomain = all_subdomains[rank]

        # check that the number of grid points in each local domain is 
        # larger than the number of halo cells
        for i in range(n_dims):
            if n_procs[i] == 1:  # skip shared axes
                continue
            if my_subdomain.inner_shape[i] < halo:
                raise ValueError(
                    f"Number of grid points in the direction {i} is too small. "
                    f"Add more grid points or reduce the number of halo cells.")

        # --------------------------------------------------------------
        #  Prepare the halo exchange
        # --------------------------------------------------------------
        # exchange of halo regions in shared axes:
        paddings = tuple(tuple((halo, halo) if i == j else (0, 0) 
                               for i in range(n_dims))
                         for j in range(n_dims))
        inner = _make_slice_tuple(slice(halo, -halo), n_dims)

        # create subcommunicators for each axis
        subcomms = []
        for i in range(n_dims):
            subdims = [False] * n_dims
            subdims[i] = True
            subcomms.append(comm.Sub(subdims))
        
        # get the neighbors for each axis
        neighbors = [s.Shift(0, 1) for s in subcomms]
        prev_proc = [n[0] for n in neighbors]
        next_proc = [n[1] for n in neighbors]

        # create slices for halo exchange
        send_to_next = _make_slice_tuple(slice(-2*halo, -halo), n_dims)
        send_to_prev = _make_slice_tuple(slice(halo, 2*halo), n_dims)
        recv_from_next = _make_slice_tuple(slice(-halo, None), n_dims)
        recv_from_prev = _make_slice_tuple(slice(None, halo), n_dims)

        # --------------------------------------------------------------
        #  Set the attributes
        # --------------------------------------------------------------

        # public readable attributes
        self._n_dims = n_dims           # number of dimensions
        self._n_global = n_global       # total number of grid points
        self._halo = halo               # number of halo cells
        self._n_procs = n_procs         # number of processors in each direction
        self._shared_axes = shared_axes # axes that are shared between processors
        self._comm = comm               # communicator
        self._size = size               # number of processors
        self._rank = rank               # rank of this processor
        self._all_subdomains = all_subdomains  # list of all subdomains
        self._my_subdomain = my_subdomain  # subdomain of this processor

        # private attributes
        self._subcomms = subcomms
        self._next_proc = next_proc
        self._prev_proc = prev_proc
        self._send_to_next = send_to_next
        self._send_to_prev = send_to_prev
        self._recv_from_next = recv_from_next
        self._recv_from_prev = recv_from_prev
        self._paddings = paddings
        self._inner = inner
        return

    @partial(utils.jaxjit, static_argnames='flat_axes')
    def sync(self, arr: np.ndarray, flat_axes: list | None = None) -> None:
        """
        # Synchronize Halos
        Synchronize the halo regions of an array between neighboring domains.
        
        Description
        -----------
        This function synchronizes the halo regions of an array between neighboring
        domains. The synchronization is done in place (no return value). 
        Synchronization is always periodic in all directions.
        
        Parameters
        ----------
        `arr` : `ndarray`
            The array to synchronize.
        `flat_axes` : `list[int]`, optional (default=None)
            A list of axes to skip synchronization.
        
        Examples
        --------
        .. code-block:: python

            from fridom.framework import config
            from fridom.framework.domain_decomposition import DomainDecomposition
            # create a domain decomposition
            domain = DomainDecomposition(n_global=(128, 128), shared_axes=[0])
            # create a random array on the local domain
            u = config.ncp.random.rand(domain.my_subdomain.shape)
            # synchronize the halo regions between neighboring domains
            domain.sync(u)
        """
        return self.sync_multiple((arr,), flat_axes)[0]

    @partial(utils.jaxjit, static_argnames='flat_axes')
    def sync_multiple(self, 
                      arrs: 'tuple[np.ndarray]', 
                      flat_axes: list | None = None) -> tuple[np.ndarray]:
        """
        Synchronize the halo regions of multiple arrays between neighboring domains.
        
        Description
        -----------
        This function synchronizes the halo regions of a tuple of arrays between
        neighboring domains. The synchronization is done in place (no return value).
        Synchronization is always periodic in all directions.
        
        Parameters
        ----------
        `arrs` : `tuple[ndarray]`
            List of arrays to synchronize.
        `flat_axes` : `list[int]`, optional (default=None)
            A list of axes to skip synchronization.
        
        Returns
        -------
        `tuple[ndarray]`
            The tuple of arrays with the halo regions synchronized.
        
        Examples
        --------
        .. code-block:: python

            from fridom.framework import config
            from fridom.framework.domain_decomposition import DomainDecomposition
            # create a domain decomposition
            domain = DomainDecomposition(n_global=(128, 128), shared_axes=[0])
            # create a random array on the local domain
            u = config.ncp.random.rand(domain.my_subdomain.shape)
            v = config.ncp.random.rand(domain.my_subdomain.shape)
            # synchronize the halo regions between neighboring domains
            u, v = domain.sync_multiple((u, v))
        """
        # nothing to do if there are no halo regions
        if self.halo == 0:
            return arrs

        flat_axes = flat_axes or []
        
        # synchronize cpu and gpu
        self.sync_with_device()

        # synchronize one dimension at a time
        for axis in range(self.n_dims):
            if axis in flat_axes:
                continue
            if self._n_procs[axis] == 1:
                arrs = self._sync_axis_same_proc(arrs, axis)
            else:
                arrs = self._sync_axis(arrs, axis)
        return arrs

    @partial(utils.jaxjit, static_argnames=['axis'])
    def _sync_axis_same_proc(self, arrs: tuple[np.ndarray], 
                            axis: int,) -> tuple[np.ndarray]:
        if self.n_global[axis] < self.halo:
            pad = config.ncp.pad
            ics = self.inner[axis]
            pad_width = self.paddings[axis]
            return tuple(pad(arr[ics], pad_width, mode='wrap') for arr in arrs)
        else:
            rfn = self._recv_from_next[axis]
            rfp = self._recv_from_prev[axis]
            stn = self._send_to_next[axis]
            stp = self._send_to_prev[axis]
            if config.backend_is_jax:
                arrs = tuple(arr.at[rfn].set(arr[stp]) for arr in arrs)
                arrs = tuple(arr.at[rfp].set(arr[stn]) for arr in arrs)
            else:
                for arr in arrs:
                    arr[rfn] = arr[stp]
                    arr[rfp] = arr[stn]
            return arrs

    @partial(utils.jaxjit, static_argnames='axis')
    def _sync_axis(self, arrs: tuple[np.ndarray], axis: int) -> tuple[np.ndarray]:
        reqs = []

        # we need to create 4 buffers for each dimension:
        #  - buf_send_next: buffer to be sent to the next processor
        #  - buf_send_prev: buffer to be sent to the previous processor
        #  - buf_recv_next: buffer to receive data from the next processor
        #  - buf_recv_prev: buffer to receive data from the previous processor
        #
        #            buf_send_prev          buf_send_next
        # |                v                      v                |
        # |-----------|----------+-----------+---------|-----------|
        # |     ^                                            ^     |
        #  buf_recv_prev                               buf_recv_next

        # ----------------------------------------------------------------
        #  Sending
        # ----------------------------------------------------------------
        ncp = config.ncp
        for arr in arrs:
            buf_send_next = ncp.ascontiguousarray(arr[self._send_to_next[axis]])
            buf_send_prev = ncp.ascontiguousarray(arr[self._send_to_prev[axis]])
            self.sync_with_device()
            reqs.append(self._subcomms[axis].Isend(
                buf_send_next, dest=self._next_proc[axis], tag=0))
            reqs.append(self._subcomms[axis].Isend(
                buf_send_prev, dest=self._prev_proc[axis], tag=0))

        # ----------------------------------------------------------------
        #  Receiving
        # ----------------------------------------------------------------
        buf_recv_next_list = []
        buf_recv_prev_list = []
        for arr in arrs:
            buf_recv_next = ncp.empty_like(arr[self._recv_from_next[axis]])
            buf_recv_prev = ncp.empty_like(arr[self._recv_from_prev[axis]])
            reqs.append(self._subcomms[axis].Irecv(
                buf_recv_next, source=self._next_proc[axis], tag=0))
            reqs.append(self._subcomms[axis].Irecv(
                buf_recv_prev, source=self._prev_proc[axis], tag=0))
            buf_recv_next_list.append(buf_recv_next)
            buf_recv_prev_list.append(buf_recv_prev)

        # wait for all non-blocking operations to complete
        MPI.Request.Waitall(reqs)

        # copy the received data to the halo regions
        for i, arr in enumerate(arrs):
            arr[self._recv_from_next[axis]] = buf_recv_next_list[i]
            arr[self._recv_from_prev[axis]] = buf_recv_prev_list[i]
        return arrs

    @partial(utils.jaxjit, static_argnames=['axis', 'side'])
    def apply_boundary_condition(
            self, 
            arr: np.ndarray, 
            bc: np.ndarray, 
            axis: int, 
            side: str
            ) -> np.ndarray:
        """
        Apply boundary condition to the halo regions of an array.
        
        Parameters
        ----------
        `arr` : `np.ndarray`
            The array to apply the boundary condition to.
        `bc` : `np.ndarray`
            The boundary condition to apply.
        `axis` : `int`
            The dimension to apply the boundary condition to.
        `side` : `str`
            The side to apply the boundary condition to. left or right.

        Returns
        -------
        `np.ndarray`
            The array with the boundary condition applied.
        
        Raises
        ------
        `ValueError`
            f `side` is not either 'left' or 'right'.
        """
        if self.halo == 0:
            return arr  # nothing to do if there are no halo regions
        if side == "left":
            return self._apply_left_boundary_condition(arr, bc, axis)
        elif side == "right":
            return self._apply_right_boundary_condition(arr, bc, axis)
        else:
            raise ValueError("side must be either 'left' or 'right'.")

    @partial(utils.jaxjit, static_argnames=['axis'])
    def _apply_left_boundary_condition(
            self, arr: np.ndarray, bc: np.ndarray, axis: int) -> np.ndarray:
        # apply the boundary condition to the left side
        if self.my_subdomain.is_left_edge[axis]:
            arr[self._recv_from_prev[axis]] = bc
        return arr
    
    @partial(utils.jaxjit, static_argnames=['axis'])
    def _apply_right_boundary_condition(
            self, arr: np.ndarray, bc: np.ndarray, axis: int) -> np.ndarray:
        # apply the boundary condition to the right side
        if self.my_subdomain.is_right_edge[axis]:
            arr[self._recv_from_next[axis]] = bc
        return arr

    def sync_with_device(self):
        """
        Synchronize the gpu device with the processor.
        
        Description
        -----------
        When using the cupy backend, and calling a cupy function, the cpu does
        not wait for the gpu to finish the computation. This can lead to the cpu
        and gpu being out of sync. This function ensures that the cpu waits for
        all gpu computations to finish.
        """
        if config.backend == "cupy":
            config.ncp.cuda.Stream.null.synchronize()

    def __deepcopy__(self, memo) -> 'DomainDecomposition':
        deepcopy_obj = object.__new__(self.__class__)
        memo[id(self)] = deepcopy_obj  # Store in memo to handle self-references
        for key, value in vars(self).items():
            if isinstance(value, list):
                list_copy = []
                for item in value:
                    if isinstance(item, MPI.Cartcomm):
                        list_copy.append(item)
                    else:
                        list_copy.append(deepcopy(item, memo))
                setattr(deepcopy_obj, key, list_copy)
            # check if value is of type mpi4py.MPI.Cartcomm
            elif isinstance(value, MPI.Cartcomm):
                setattr(deepcopy_obj, key, value)
            else:
                setattr(deepcopy_obj, key, deepcopy(value, memo))
        return deepcopy_obj

    def __del__(self):
        try:
            self._comm.Free()
        except:
            pass
        return

    def __reduce__(self):
        args = (self._n_global, self._halo, self._shared_axes)
        return (self.__class__, args)

    def __setstate__(self, state):
        self.__init__(*state)
        return self

    # ================================================================
    #  Properties
    # ================================================================
    @property
    def n_dims(self) -> int:
        """The number of dimensions."""
        return self._n_dims

    @property
    def n_global(self) -> tuple[int]:
        """The total number of grid points in each dimension."""
        return self._n_global

    @property
    def halo(self) -> int:
        """The number of halo cells (ghost cells) around the local domain."""
        return self._halo

    @property
    def n_procs(self) -> tuple[int]:
        """The number of processors in each direction."""
        return self._n_procs

    @property
    def shared_axes(self) -> list[int]:
        """A list of axes that are shared between processors."""
        return self._shared_axes

    @property
    def comm(self) -> MPI.Intracomm:
        """The cartesian communicator that defines the processor grid."""
        return self._comm

    @property
    def size(self) -> int:
        """The total number of processors."""
        return self._size

    @property
    def rank(self) -> int:
        """The rank of the current processor."""
        return self._rank

    @property
    def all_subdomains(self) -> list[Subdomain]:
        """A list of all subdomains in the global domain."""
        return self._all_subdomains

    @property
    def my_subdomain(self) -> Subdomain:
        """The local domain of the current processor."""
        return self._my_subdomain

utils.jaxify_class(DomainDecomposition)