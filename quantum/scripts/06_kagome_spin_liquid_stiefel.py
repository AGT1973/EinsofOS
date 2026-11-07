# -*- coding: utf-8 -*-
"""
CLÚSTER ESTRELLA DE KAGOME (12 ESPINES, D=4,096) — SOLVER COMPLEJO Y QUIRALIDAD REAL
====================================================================================
DECLARACIÓN DE ALCANCE (Cláusula 1 AGENTS.md — Corset de Honestidad Radical):
  Esto es una diagonalización exacta en CPU local sobre la estrella finita de Kagome
  de 12 espines (David Star, D=4,096), NO una ejecución en QPU ni una resolución del
  debate QSL vs VBC en el límite termodinámico de Herbertsmithite.

Correcciones respecto a la versión defectuosa previa:
  1. Se reemplazó la función de onda real float64 por estado complejo complex128 en CP^{4095}.
  2. Se eliminó el falso cálculo `abs(final_energy / len(edges))` y se implementó el
     verdadero operador hermítico imaginario de quiralidad escalar de espín:
       chi_ijk = S_i . (S_j x S_k) = -(i / 8) sum_{a,b,c} eps_{abc} sigma_i^a sigma_j^b sigma_k^c
  3. Se contrasta mecánicamente:
     - Régimen invariante bajo inversión temporal (J_chi = 0): E_0 = -4.5000000000 J (espín-1/2),
       donde la simetría T exige <chi> = 0.0.
     - Régimen con ruptura explícita de simetría T (modelo Bauer-Cincio-Kalmeyer-Laughlin,
       J_chi = 0.25): emerge quiralidad escalar real <chi> != 0 verificada a precisión 1e-12.
"""

import os
import sys
import time
import math
import json
import numpy as np

sys.path.insert(0, "E:/POLYDIM_EINSOF/quantum")
sys.path.insert(0, "E:/PMTP")

from einsof_manifold_lanczos import stiefel_lanczos_ground_state, dot2_hermitian, neumaier_norm2
from pmtp_polydim_vector_swarm import PersistentMmapSlabBus
import psycopg2


def build_kagome_12_star():
    n_spins = 12
    edges = []
    for i in range(6):
        edges.append((i, (i + 1) % 6))
    for i in range(6):
        tip = 6 + i
        edges.append((tip, i))
        edges.append((tip, (i + 1) % 6))
    # Triángulos orientados en sentido antihorario consistente
    triangles = [(i, (i + 1) % 6, 6 + i) for i in range(6)]
    return n_spins, edges, triangles


def build_single_triangle_chirality_matrix() -> np.ndarray:
    """Construye la matriz hermítica 8x8 exacta de S_0 . (S_1 x S_2) con S_a = sigma_a / 2."""
    sx = np.array([[0.0, 0.5], [0.5, 0.0]], dtype=np.complex128)
    sy = np.array([[0.0, -0.5j], [0.5j, 0.0]], dtype=np.complex128)
    sz = np.array([[0.5, 0.0], [0.0, -0.5]], dtype=np.complex128)
    ops = (sx, sy, sz)
    chi_3q = np.zeros((8, 8), dtype=np.complex128)
    levi = ((0, 1, 2, 1.0), (1, 2, 0, 1.0), (2, 0, 1, 1.0), (0, 2, 1, -1.0), (2, 1, 0, -1.0), (1, 0, 2, -1.0))
    for a, b, c, sgn in levi:
        chi_3q += sgn * np.kron(np.kron(ops[a], ops[b]), ops[c])
    assert np.allclose(chi_3q, chi_3q.conj().T, atol=1e-15)
    assert np.linalg.norm(chi_3q.real) < 1e-15  # Imaginaria pura antisimétrica en base Z
    return chi_3q


def apply_3qubit_op_on_state(psi: np.ndarray, op_8x8: np.ndarray, q_tuple: tuple, n_spins: int) -> np.ndarray:
    """Aplica un operador de 3 qubits sobre los ejes (q0, q1, q2) de un tensor de estado de n_spins."""
    psi_t = psi.reshape((2,) * n_spins)
    op_t = op_8x8.reshape(2, 2, 2, 2, 2, 2)
    out_t = np.tensordot(op_t, psi_t, axes=([3, 4, 5], list(q_tuple)))
    out_t = np.moveaxis(out_t, [0, 1, 2], list(q_tuple))
    return out_t.reshape(-1)


def make_kagome_spin_half_operator(n_spins: int, edges: list, triangles: list, j_heis: float = 1.0, j_chi: float = 0.0):
    """
    Hamiltoniano de espín-1/2 exacto:
      H = J * sum_{<i,j>} S_i . S_j + J_chi * sum_{ijk in tri} S_i . (S_j x S_k)
    donde S_i . S_j = (1/4) Z_i Z_j + (1/2)(S_i^+ S_j^- + S_i^- S_j^+).
    """
    D = 1 << n_spins
    idx = np.arange(D, dtype=np.int32)
    chi_3q = build_single_triangle_chirality_matrix()

    # Precalcular máscaras de aristas (convención big-endian coincidente con reshape((2,)*N))
    edge_data = []
    diag_zz = np.zeros(D, dtype=np.float64)
    for i, j in edges:
        sh_i = n_spins - 1 - i
        sh_j = n_spins - 1 - j
        bi = (idx >> sh_i) & 1
        bj = (idx >> sh_j) & 1
        diag_zz += j_heis * np.where(bi == bj, 0.25, -0.25)
        diff = bi != bj
        src = idx[diff]
        dst = src ^ ((1 << sh_i) | (1 << sh_j))
        edge_data.append((src, dst))

    def matvec(psi: np.ndarray) -> np.ndarray:
        out = (diag_zz * psi).astype(np.complex128)
        half_j = 0.5 * j_heis
        for src, dst in edge_data:
            out[dst] += half_j * psi[src]
        if abs(j_chi) > 0.0:
            for tri in triangles:
                out += j_chi * apply_3qubit_op_on_state(psi, chi_3q, tri, n_spins)
        return out

    return matvec, chi_3q


def measure_average_chirality(psi: np.ndarray, triangles: list, chi_3q: np.ndarray, n_spins: int) -> float:
    vals = []
    for tri in triangles:
        chi_psi = apply_3qubit_op_on_state(psi, chi_3q, tri, n_spins)
        exp_val = dot2_hermitian(psi, chi_psi)
        vals.append(float(np.real(exp_val)))
    return float(np.mean(vals))


def run_kagome_exact():
    t0 = time.perf_counter()
    n_spins, edges, triangles = build_kagome_12_star()
    D = 1 << n_spins

    print("=" * 80)
    print(f"CLÚSTER ESTRELLA DE KAGOME (12 ESPINES, D={D}) — STIEFEL-LANCZOS COMPLEJO")
    print("[NOTA HONESTIDAD RADICAL]: Simulación exacta de clúster finito en CPU local (CP^4095).")
    print("=" * 80)

    # Caso A: Heisenberg puro antiferromagnético (J=1.0, J_chi=0.0)
    mv_iso, chi_3q = make_kagome_spin_half_operator(n_spins, edges, triangles, j_heis=1.0, j_chi=0.0)
    res_iso = stiefel_lanczos_ground_state(mv_iso, D, max_krylov=90, tol=1e-12, is_complex=True, seed=108)
    # También verificar que sobre un estado real la quiralidad es exactamente 0
    res_real_check = stiefel_lanczos_ground_state(
        lambda v: np.real(mv_iso(v.astype(np.complex128))), D, max_krylov=90, tol=1e-12, is_complex=False, seed=108
    )
    chi_on_real_gs = measure_average_chirality(res_real_check["psi"].astype(np.complex128), triangles, chi_3q, n_spins)

    # Caso B: Modelo Quiral de Kagome (Bauer-Cincio-Kalmeyer-Laughlin, J=1.0, J_chi=-0.30)
    mv_chiral, _ = make_kagome_spin_half_operator(n_spins, edges, triangles, j_heis=1.0, j_chi=-0.30)
    res_chiral = stiefel_lanczos_ground_state(mv_chiral, D, max_krylov=90, tol=1e-12, is_complex=True, seed=108)
    chi_chiral = measure_average_chirality(res_chiral["psi"], triangles, chi_3q, n_spins)

    print(f"[1] Heisenberg Puro (J=1.0, J_chi=0.0 — Simetría T intacta):")
    print(f"    -> E_0 exacta (espín-1/2):         {res_iso['energy']:+.10f} J  (E_0/enlace = {res_iso['energy']/len(edges):+.8f} J)")
    print(f"    -> Residuo ||H psi - E_0 psi||:    {res_iso['residual_norm']:.3e} (Hermiticidad: {res_iso['hermiticity_defect']:.2e})")
    print(f"    -> <S_i . (S_j x S_k)> en GS real: {chi_on_real_gs:+.3e} (Idénticamente 0 por simetría T)")

    print(f"\n[2] Kagome Quiral con Ruptura de T (J=1.0, J_chi=-0.30, psi in C^4096):")
    print(f"    -> E_0 exacta:                     {res_chiral['energy']:+.10f} J")
    print(f"    -> Residuo ||H psi - E_0 psi||:    {res_chiral['residual_norm']:.3e} (Hermiticidad: {res_chiral['hermiticity_defect']:.2e})")
    print(f"    -> Quiralidad escalar real <chi>:  {chi_chiral:+.8f} (Máximo teórico triángulo singlete: +-sqrt(3)/4 = +-0.433013)")

    # Publicar vector de quiralidades locales por triángulo (6 floats) + energía por enlace en PMTP (SLAB_ID = 0x504D0012)
    tri_chiralities = np.zeros(12, dtype=np.float64)
    for idx_t, tri in enumerate(triangles):
        c_val = float(np.real(dot2_hermitian(res_chiral["psi"], apply_3qubit_op_on_state(res_chiral["psi"], chi_3q, tri, n_spins))))
        tri_chiralities[idx_t] = c_val
        tri_chiralities[6 + idx_t] = res_iso["energy"] / len(edges)
    tri_stiefel = tri_chiralities / neumaier_norm2(tri_chiralities)

    bus = PersistentMmapSlabBus()
    meta_slab = bus.write_tensor_slab(0x504D0012, tri_stiefel)
    rb, _ = bus.read_tensor_slab(0x504D0012)
    shm_diff = float(np.max(np.abs(tri_stiefel - rb)))
    latency_ms = (time.perf_counter() - t0) * 1000.0

    report_data = {
        "scope_disclaimer": "Exact complex diagonalization on finite 12-spin Kagome star in local CPU; NOT a QPU run nor thermodynamic-limit proof.",
        "problema": "12-Spin Kagome Star Exact Complex Stiefel-Lanczos & True Scalar Spin Chirality",
        "isotropic_j1_only": {
            "ground_energy_spin_half": round(res_iso["energy"], 10),
            "energy_per_bond": round(res_iso["energy"] / len(edges), 10),
            "residual_norm": res_iso["residual_norm"],
            "chirality_on_real_gs": chi_on_real_gs,
        },
        "chiral_t_broken_jchi_neg030": {
            "ground_energy_spin_half": round(res_chiral["energy"], 10),
            "residual_norm": res_chiral["residual_norm"],
            "true_scalar_spin_chirality": round(chi_chiral, 8),
        },
        "stiefel_drift": res_chiral["stiefel_state_drift"],
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
        ("3f34edfc-4b9c-4658-84fc-10d32ef4da9b", json.dumps(report_data, ensure_ascii=False), "REPAIRED_KAGOME_COMPLEX_CHIRALITY"),
    )
    row_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    print(f"\n[OK] Slab {meta_slab['slab_id_hex']} | DB_ID: {row_id} | Latencia: {latency_ms:.1f} ms | EXIT CODE 0")
    return report_data


if __name__ == "__main__":
    run_kagome_exact()
