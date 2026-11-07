# -*- coding: utf-8 -*-
"""
MODELO DE HUBBARD 1D A MEDIO LLENADO (8 SITIOS, D=4,900) — SOLVER HERMÍTICO EXACTO
==================================================================================
DECLARACIÓN DE ALCANCE (Cláusula 1 AGENTS.md — Corset de Honestidad Radical):
  Esto es una simulación teórica exacta por diagonalización de Lanczos en CPU local
  sobre un anillo finito de 8 sitios (16 espín-orbitales, D = C(8,4)^2 = 4,900),
  NO una ejecución física en hardware cuántico ni una prueba en el límite termodinámico.

Correcciones respecto a la versión defectuosa previa:
  1. Se restauró el término conjugado hermítico '+ h.c.' (salto j -> i además de i -> j)
     con signo fermiónico exacto de Jordan-Wigner; se verifica ||H - H^dagger|| <= 1e-15.
  2. Se reemplazaron los 30 pasos de gradiente por Stiefel-Lanczos reortogonalizado
     con parada por residuo propio ||H|psi> - E_0|psi>||_2 <= 1e-12.
  3. Validación analítica cruzada en U = 0 contra el espectro exacto de ondas de Bloch.
"""

import os
import sys
import time
import math
import json
from itertools import combinations
import numpy as np

sys.path.insert(0, "E:/POLYDIM_EINSOF/quantum")
sys.path.insert(0, "E:/PMTP")

from einsof_manifold_lanczos import stiefel_lanczos_ground_state, neumaier_norm2
from pmtp_polydim_vector_swarm import PersistentMmapSlabBus
import psycopg2


def build_1d_hubbard_ring_operator(n_sites: int = 8, n_elec_spin: int = 4, t_hop: float = 1.0, u_on: float = 4.0):
    up_configs = [sum(1 << p for p in pos) for pos in combinations(range(n_sites), n_elec_spin)]
    n_single = len(up_configs)  # C(8,4) = 70
    cfg_map = {cfg: idx for idx, cfg in enumerate(up_configs)}
    D = n_single * n_single     # 4,900

    # Matriz cinética 1-partícula T_1p (70 x 70) con i -> j Y j -> i (+ h.c. obligatorio!)
    T_1p = np.zeros((n_single, n_single), dtype=np.float64)
    for idx_src, cfg in enumerate(up_configs):
        for i in range(n_sites):
            j = (i + 1) % n_sites
            # Ambos sentidos del enlace no dirigido {i, j}: i->j y j->i (+ h.c.)
            for src_site, dst_site in ((i, j), (j, i)):
                if ((cfg >> src_site) & 1) and not ((cfg >> dst_site) & 1):
                    new_cfg = (cfg ^ (1 << src_site)) | (1 << dst_site)
                    idx_dst = cfg_map[new_cfg]
                    low, high = min(src_site, dst_site), max(src_site, dst_site)
                    between_mask = ((1 << (high - low - 1)) - 1) << (low + 1)
                    parity = (cfg & between_mask).bit_count() % 2
                    sign = -1.0 if parity else 1.0
                    T_1p[idx_dst, idx_src] += -t_hop * sign

    herm_err = float(np.linalg.norm(T_1p - T_1p.T, ord="fro"))
    assert herm_err < 1e-14, f"VIOLACIÓN DE HERMITICIDAD EN T_1p: {herm_err}"

    double_occ_vec = np.zeros(D, dtype=np.float64)
    for u_i, cu in enumerate(up_configs):
        base = u_i * n_single
        for d_i, cd in enumerate(up_configs):
            double_occ_vec[base + d_i] = float((cu & cd).bit_count())

    diag_U = u_on * double_occ_vec

    def matvec(psi: np.ndarray) -> np.ndarray:
        Psi_mat = psi.reshape(n_single, n_single)
        kin = (T_1p @ Psi_mat) + (Psi_mat @ T_1p.T)
        return kin.ravel() + diag_U * psi

    return matvec, up_configs, double_occ_vec, D


def exact_bloch_u0_energy(n_sites: int = 8, n_elec_spin: int = 4, t_hop: float = 1.0) -> float:
    """Energía analítica exacta del estado fundamental en U=0 (niveles de momento k = 2*pi*m / L)."""
    ks = [2.0 * math.pi * m / n_sites for m in range(n_sites)]
    eps = sorted(-2.0 * t_hop * math.cos(k) for k in ks)
    return 2.0 * sum(eps[:n_elec_spin])


def run_mott_hubbard_exact():
    t0 = time.perf_counter()
    n_sites = 8
    n_elec = 4
    print("=" * 80)
    print("MODELO DE HUBBARD 1D (8 SITIOS, D=4,900) — STIEFEL-LANCZOS HERMÍTICO EXACTO")
    print("[NOTA HONESTIDAD RADICAL]: Simulación teórica exacta de clúster finito en CPU local.")
    print("=" * 80)

    # 1. Verificación analítica obligatoria en U = 0
    mv_u0, up_configs, double_occ_vec, D = build_1d_hubbard_ring_operator(n_sites, n_elec, t_hop=1.0, u_on=0.0)
    res_u0 = stiefel_lanczos_ground_state(mv_u0, D, max_krylov=80, tol=1e-12, seed=77)
    e_analytic_u0 = exact_bloch_u0_energy(n_sites, n_elec, t_hop=1.0)
    err_u0 = abs(res_u0["energy"] - e_analytic_u0)
    print(f"[Control Analítico U=0] E_Lanczos = {res_u0['energy']:.12f} | E_Bloch = {e_analytic_u0:.12f} | |err| = {err_u0:.2e}")
    assert err_u0 < 1e-10, f"Fallo en control analítico U=0: {err_u0}"

    # 2. Barrido físico U/t in {2.0, 4.0, 8.0}: supresión continua de doble ocupación (crossover de Mott en 1D)
    sweep_results = []
    psi_u4 = None
    res_u4 = None
    for u_val in (0.0, 2.0, 4.0, 8.0):
        mv, _, _, _ = build_1d_hubbard_ring_operator(n_sites, n_elec, t_hop=1.0, u_on=u_val)
        res = stiefel_lanczos_ground_state(mv, D, max_krylov=90, tol=1e-12, seed=2026)
        d_occ = float(np.dot(res["psi"] ** 2, double_occ_vec)) / n_sites
        sweep_results.append({
            "U_over_t": u_val,
            "ground_energy": round(res["energy"], 10),
            "energy_per_site": round(res["energy"] / n_sites, 10),
            "double_occupancy": round(d_occ, 6),
            "residual_norm": res["residual_norm"],
            "hermiticity_defect": res["hermiticity_defect"],
            "matvecs": res["matvecs"],
        })
        print(
            f"  U/t = {u_val:4.1f} | E_0 = {res['energy']:+12.8f} t | <n_up n_dn> = {d_occ:.6f} "
            f"| res = {res['residual_norm']:.2e} | herm_err = {res['hermiticity_defect']:.2e}"
        )
        if u_val == 4.0:
            psi_u4 = res["psi"]
            res_u4 = res

    # 3. Ocupaciones por sitio en U/t = 4.0 publicadas en PMTP (SLAB_ID = 0x504D0008)
    n_single = len(up_configs)
    Psi_mat = psi_u4.reshape(n_single, n_single)
    prob_up = np.sum(Psi_mat ** 2, axis=1)
    prob_dn = np.sum(Psi_mat ** 2, axis=0)
    site_occ = np.zeros(n_sites, dtype=np.float64)
    for i in range(n_sites):
        mask = 1 << i
        has_bit = np.array([(c & mask) != 0 for c in up_configs], dtype=np.float64)
        site_occ[i] = float(np.dot(prob_up, has_bit) + np.dot(prob_dn, has_bit))

    occ_stiefel = site_occ / neumaier_norm2(site_occ)
    bus = PersistentMmapSlabBus()
    meta_slab = bus.write_tensor_slab(0x504D0008, occ_stiefel)
    rb, _ = bus.read_tensor_slab(0x504D0008)
    shm_diff = float(np.max(np.abs(occ_stiefel - rb)))
    latency_ms = (time.perf_counter() - t0) * 1000.0

    report_data = {
        "scope_disclaimer": "Exact finite-cluster CPU diagonalization (8-site 1D ring, D=4900); NOT physical QPU execution nor thermodynamic-limit proof.",
        "problema": "1D Hubbard Half-Filling Exact Hermitian Lanczos (8 sites, D=4900)",
        "analytic_u0_error": err_u0,
        "u_sweep": sweep_results,
        "u4_ground_energy": round(res_u4["energy"], 10),
        "u4_residual_norm": res_u4["residual_norm"],
        "stiefel_drift": res_u4["stiefel_state_drift"],
        "shm_diff": shm_diff,
        "pmtp_slab_id": meta_slab["slab_id_hex"],
        "latencia_ms": round(latency_ms, 2),
        "exit_code": 0,
    }

    conn = psycopg2.connect("dbname=polydim_vec_db user=postgres password=postgres host=localhost port=5432")
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO session_context (conversation_id, summary, category, created_at)
        VALUES (%s, %s, %s, NOW())
        RETURNING id;
        """,
        ("3f34edfc-4b9c-4658-84fc-10d32ef4da9b", json.dumps(report_data, ensure_ascii=False), "REPAIRED_HUBBARD_1D_HERMITIAN_LANCZOS"),
    )
    row_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    print(f"[OK] Slab {meta_slab['slab_id_hex']} | DB_ID: {row_id} | Tiempo total: {latency_ms:.1f} ms | EXIT CODE 0")
    return report_data


if __name__ == "__main__":
    run_mott_hubbard_exact()
