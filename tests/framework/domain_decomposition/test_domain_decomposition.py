import pytest
from mpi4py import MPI
from copy import deepcopy
import fridom.framework as fr

@pytest.fixture(params=[0, 1, 4], ids=["halo_0", "halo_1", "halo_4"])
def halo(request):
    return request.param

@pytest.mark.parametrize("n_global", [[64, 64], [64, 65], [64, 64, 63]])
def test_construction(backend, halo, n_global):
    fr.config.set_backend(backend)
    domain = fr.domain_decomposition.DomainDecomposition(
        n_global=n_global, shared_axes=[0], halo=halo)
    assert domain.n_global == n_global
    assert domain.halo == halo
    n_proc = MPI.COMM_WORLD.Get_size()
    assert len(domain.all_subdomains) == n_proc
    if n_proc != 1:
        assert domain.my_subdomain.shape != tuple(n_global)

def test_deepcopy(backend):
    domain = fr.domain_decomposition.DomainDecomposition(
        n_global=[64, 64], shared_axes=[0], halo=0)
    domain_copy = deepcopy(domain)
    assert domain != domain_copy
    assert domain.n_global == domain_copy.n_global

    # Change the copy
    domain_copy.n_global[0] = 128
    assert domain.n_global[0] != 128

@pytest.fixture(params=[0, 1])
def flat_axis(request):
    return request.param

def test_sync_topo_array(backend, flat_axis):
    ncp = fr.config.ncp
    domain = fr.domain_decomposition.DomainDecomposition(
        n_global=[64, 64], shared_axes=[0], halo=2)
    shape = list(domain.my_subdomain.shape)
    shape[flat_axis] = 1
    u = ncp.random.rand(*tuple(shape))
    domain.sync(u, flat_axes=[flat_axis])

@pytest.mark.parametrize("halo", [0, 1, 2])
def test_sync_1d_array(backend, halo):
    ncp = fr.config.ncp
    n_global = [64, 1 , 32]
    domain = fr.domain_decomposition.DomainDecomposition(
        n_global=n_global, shared_axes=[0, 1], halo=halo)
    u = ncp.random.rand(*domain.my_subdomain.shape)
    assert u.shape[1] == 1 + 2 * halo
    domain.sync(u)

    