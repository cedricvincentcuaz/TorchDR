# -*- coding: utf-8 -*-
"""
Tests for affinity matrices.
"""

# Author: Hugues Van Assel <vanasselhugues@gmail.com>
#
# License: BSD 3-Clause License

import pytest
import torch
import numpy as np
from sklearn.datasets import make_moons

from torchdr.utils import (
    check_similarity_torch_keops,
    check_symmetry,
    check_marginal,
    check_entropy,
    check_type,
    check_shape,
    check_nonnegativity,
    check_total_sum,
    entropy,
)
from torchdr.affinity import (
    ScalarProductAffinity,
    GibbsAffinity,
    StudentAffinity,
    EntropicAffinity,
    L2SymmetricEntropicAffinity,
    SymmetricEntropicAffinity,
    DoublyStochasticEntropic,
    log_Pe,
    bounds_entropic_affinity,
)

lst_types = ["float32", "float64"]

LIST_METRICS_TEST = ["euclidean", "manhattan"]
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def toy_dataset(n=300, dtype="float32"):
    X, _ = make_moons(n_samples=n, noise=0.05, random_state=0)
    return X.astype(dtype)


@pytest.mark.parametrize("dtype", lst_types)
def test_scalar_product_affinity(dtype):
    n = 300
    X = toy_dataset(n, dtype)

    list_P = []
    for keops in [False, True]:
        affinity = ScalarProductAffinity(device=DEVICE, keops=keops)
        P = affinity.fit_transform(X)
        list_P.append(P)

        # -- check properties of the affinity matrix --
        check_type(P, keops=keops)
        check_shape(P, (n, n))
        check_symmetry(P)

    # --- check consistency between torch and keops ---
    check_similarity_torch_keops(list_P[0], list_P[1], K=10)


@pytest.mark.parametrize("dtype", lst_types)
def test_gibbs_affinity(dtype):
    n = 300
    X = toy_dataset(n, dtype)
    one = torch.ones(n, dtype=getattr(torch, dtype), device=DEVICE)

    for metric in LIST_METRICS_TEST:
        for dim in [0, 1, (0, 1)]:
            list_P = []
            for keops in [False, True]:
                affinity = GibbsAffinity(
                    device=DEVICE, keops=keops, metric=metric, dim=dim
                )
                P = affinity.fit_transform(X)
                list_P.append(P)

                # -- check properties of the affinity matrix --
                check_type(P, keops=keops)
                check_shape(P, (n, n))
                check_nonnegativity(P)
                if isinstance(dim, int):
                    check_marginal(P, one, dim=dim)
                else:
                    check_total_sum(P, 1)

            # --- check consistency between torch and keops ---
            check_similarity_torch_keops(list_P[0], list_P[1], K=10)


@pytest.mark.parametrize("dtype", lst_types)
def test_student_affinity(dtype):
    n = 300
    X = toy_dataset(n, dtype)
    one = torch.ones(n, dtype=getattr(torch, dtype), device=DEVICE)

    for metric in LIST_METRICS_TEST:
        for dim in [0, 1, (0, 1)]:
            list_P = []
            for keops in [False, True]:
                affinity = StudentAffinity(
                    device=DEVICE, keops=keops, metric=metric, dim=dim
                )
                P = affinity.fit_transform(X)
                list_P.append(P)

                # -- check properties of the affinity matrix --
                check_type(P, keops=keops)
                check_shape(P, (n, n))
                check_nonnegativity(P)
                if isinstance(dim, int):
                    check_marginal(P, one, dim=dim)
                else:
                    check_total_sum(P, 1)

            # --- check consistency between torch and keops ---
            check_similarity_torch_keops(list_P[0], list_P[1], K=10)


@pytest.mark.parametrize("dtype", lst_types)
def test_entropic_affinity(dtype):
    n = 300
    X = toy_dataset(n, dtype)
    perp = 30
    tol = 1e-5
    zeros = torch.zeros(n, dtype=getattr(torch, dtype), device=DEVICE)
    ones = torch.ones(n, dtype=getattr(torch, dtype), device=DEVICE)
    target_entropy = np.log(perp) * ones + 1

    def entropy_gap(eps, C):  # function to find the root of
        return entropy(log_Pe(C, eps), log=True) - target_entropy

    for metric in LIST_METRICS_TEST:

        list_P = []
        for keops in [False, True]:
            affinity = EntropicAffinity(
                perplexity=perp,
                keops=keops,
                metric=metric,
                tol=tol,
                verbose=True,
                device=DEVICE,
            )
            log_P = affinity.fit_transform(X, log=True)
            list_P.append(log_P)

            # -- check properties of the affinity matrix --
            check_type(log_P, keops=keops)
            check_shape(log_P, (n, n))
            check_marginal(log_P, zeros, dim=1, tol=tol, log=True)
            check_entropy(log_P, target_entropy, dim=1, tol=1e-3, log=True)

            # -- check bounds on the root of entropic affinities --
            C = affinity._ground_cost_matrix(affinity.X_)
            begin, end = bounds_entropic_affinity(C, perplexity=perp)
            assert (
                entropy_gap(begin, C) < 0
            ).all(), "Lower bound of entropic affinity root is not valid."
            assert (
                entropy_gap(end, C) > 0
            ).all(), "Lower bound of entropic affinity root is not valid."

        # --- check consistency between torch and keops ---
        check_similarity_torch_keops(list_P[0], list_P[1], K=perp)


@pytest.mark.parametrize("dtype", lst_types)
def test_l2sym_entropic_affinity(dtype):
    n = 300
    X = toy_dataset(n, dtype)
    perp = 30

    for metric in LIST_METRICS_TEST:
        list_P = []
        for keops in [False, True]:
            affinity = L2SymmetricEntropicAffinity(
                perplexity=perp, keops=keops, metric=metric, verbose=True, device=DEVICE
            )
            P = affinity.fit_transform(X)
            list_P.append(P)

            # -- check properties of the affinity matrix --
            check_type(P, keops=keops)
            check_shape(P, (n, n))
            check_symmetry(P)

        # --- check consistency between torch and keops ---
        check_similarity_torch_keops(list_P[0], list_P[1], K=perp)


@pytest.mark.parametrize("dtype", lst_types)
def test_sym_entropic_affinity(dtype):
    n = 300
    X = toy_dataset(n, dtype)
    perp = 30
    tol = 1e-2
    zeros = torch.zeros(n, dtype=getattr(torch, dtype), device=DEVICE)
    ones = torch.ones(n, dtype=getattr(torch, dtype), device=DEVICE)
    target_entropy = np.log(perp) * ones + 1

    for metric in LIST_METRICS_TEST:
        for optimizer in ["Adam", "LBFGS"]:
            list_P = []
            for keops in [False, True]:
                affinity = SymmetricEntropicAffinity(
                    perplexity=perp,
                    keops=keops,
                    metric=metric,
                    tol=1e-6,
                    tolog=True,
                    verbose=True,
                    lr=1e0,
                    max_iter=2000,
                    eps_square=True,
                    device=DEVICE,
                    optimizer=optimizer,
                )
                log_P = affinity.fit_transform(X, log=True)
                list_P.append(log_P)

                # -- check properties of the affinity matrix --
                check_type(log_P, keops=keops)
                check_shape(log_P, (n, n))
                check_symmetry(log_P)
                check_marginal(log_P, zeros, dim=1, tol=tol, log=True)
                check_entropy(log_P, target_entropy, dim=1, tol=tol, log=True)

            # --- check consistency between torch and keops ---
            check_similarity_torch_keops(list_P[0], list_P[1], K=5)


@pytest.mark.parametrize("dtype", lst_types)
def test_doubly_stochastic_entropic(dtype):
    n = 300
    X = toy_dataset(n, dtype)
    eps = 1e0
    tol = 1e-3
    zeros = torch.zeros(n, dtype=getattr(torch, dtype), device=DEVICE)

    for metric in LIST_METRICS_TEST:
        list_P = []
        for keops in [False, True]:
            affinity = DoublyStochasticEntropic(
                eps=eps, keops=keops, metric=metric, tol=tol, device=DEVICE
            )
            log_P = affinity.fit_transform(X, log=True)
            list_P.append(log_P)

            # -- check properties of the affinity matrix --
            check_type(log_P, keops=keops)
            check_shape(log_P, (n, n))
            check_symmetry(log_P)
            check_marginal(log_P, zeros, dim=1, tol=tol, log=True)

        # --- check consistency between torch and keops ---
        check_similarity_torch_keops(list_P[0], list_P[1], K=10)
