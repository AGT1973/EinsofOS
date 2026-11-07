# -*- coding: utf-8 -*-
"""
=============================================================================
POLYDIM / EINSOF — 2D REPULSIVE HUBBARD CLUSTER: SINGLET PAIRING CORRELATIONS
Clúster Cuadrado Inclinado sqrt(8) x sqrt(8) (8 sitios, 6 electrones, D=3,136)
=============================================================================
DECLARACIÓN DE ALCANCE (Cláusula 1 AGENTS.md — Corset de Honestidad Radical):
  Esto es una diagonalización numérica exacta en CPU local sobre un clúster
  finito de 8 sitios (sqrt(8) x sqrt(8) de Betts con simetría exacta C_4v),
  NO una prueba en el límite termodinámico ni una ejecución en QPU físico.

Metodología verificada sin valores hardcodeados:
  1. Retículo cuadrado inclinado T1=(2,2), T2=(2,-2) con 8 sitios y 16 enlaces
     ortogonales exactos (8 en dirección +x con f_d=+1, 8 en dirección +y con f_d=-1).
  2. Régimen dopado (delta = 25%): N_up = 3, N_dn = 3 -> D = C(8,3)^2 = 3,136.
  3. Solver Stiefel-Lanczos Matrix-Free (einsof_manifold_lanczos) con verificación
     de hermiticidad y parada por residuo propio ||H|psi> - E_0|psi>||_2 <= 1e-11.
  4. Cálculo cuántico exacto de correlaciones de apareamiento singlete de 2 cuerpos
     directamente sobre las amplitudes de Fock convergidas |psi_0>:
       Delta_b = (c_{i,up} c_{j,dn} + c_{j,up} c_{i,dn}) / sqrt(2)
       P_alpha = (1 / N_bonds) * sum_{b, b'} f_alpha(b) f_alpha(b') <psi_0| Delta_b^dagger Delta_{b'} |psi_0>
     comparando además correlación total vs desconectada (U=0) e intrínseca de vértice.
=============================================================================
"""

import os
import sys
import time
import math
import json
import itertools
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "E:/POLYDIM_EINSOF/quantum")
sys.path.insert(0, "E:/PMTP")

from einsof_manifold_lanczos import stiefel_lanczos_ground_state, neumaier_norm2
from pmtp_polydim_vector_swarm import PersistentMmapSlabBus
import psycopg2


def build_betts_sqrt8_cluster():
    """
    Construye geométricamente el clúster cuadrado inclinado 8A (Betts) con
    vectores de supercelda T1 = (2, 2), T2 = (2, -2) -> det = 8 sitios, simetría exacta C_4v.
    """
    def wrap_coord(x: int, y: int):
        # Coordenadas reducidas en la celda fundamental de T1=(2,2), T2=(2,-2):
        # u = x + y (mod 4), v = x - y (mod 4) con u == v (mod 2) -> 4 * 2 = 8 representantes únicos
        u = (x + y) % 4
        v = (x - y) % 4
        return (u, v)

    rep_set = []
    seen = set()
    for x in range(4):
        for y in range(4):
            key = wrap_coord(x, y)
            if key not in seen:
                seen.add(key)
                rep_set.append((x, y, key))
    assert len(rep_set) == 8
    key_to_site = {item[2]: idx for idx, item in enumerate(rep_set)}

    bonds = []
    for site_idx, (x, y, _) in enumerate(rep_set):
        nx_site = key_to_site[wrap_coord(x + 1, y)]
        ny_site = key_to_site[wrap_coord(x, y + 1)]
        bonds.append((site_idx, nx_site, +1.0))  # enlace +x: f_d = +1, f_s = +1
        bonds.append((site_idx, ny_site, -1.0))  # enlace +y: f_d = -1, f_s = +1
    return bonds


def build_hubbard_8site_operator(bonds, t_hop: float = 1.0, u_on: float = 6.0):
    up_configs = list(itertools.combinations(range(8), 3))  # 56 estados
    n_single = len(up_configs)
    up_map = {conf: idx for idx, conf in enumerate(up_configs)}
    D = n_single * n_single  # 3,136 estados

    # Matriz cinética de 1 espín (56 x 56), estrictamente simétrica (hermítica)
    T_spin = np.zeros((n_single, n_single), dtype=np.float64)
    for idx_src, conf in enumerate(up_configs):
        conf_set = set(conf)
        for s1, s2, _ in bonds:
            for src, dst in ((s1, s2), (s2, s1)):
                if (src in conf_set) and (dst not in conf_set):
                    new_conf = tuple(sorted((conf_set - {src}) | {dst}))
                    idx_dst = up_map[new_conf]
                    low, high = min(src, dst), max(src, dst)
                    n_between = sum(1 for p in conf if low < p < high)
                    sign = -1.0 if (n_between % 2 == 1) else 1.0
                    # Cada enlace dirigido aparece una vez en build_betts_sqrt8_cluster
                    T_spin[idx_dst, idx_src] += -t_hop * sign

    herm_err_1p = float(np.linalg.norm(T_spin - T_spin.T, ord="fro"))
    assert herm_err_1p < 1e-14, f"T_spin no simétrica: {herm_err_1p}"

    # Vector diagonal de ocupación doble U * n_{i,up} n_{i,dn}
    double_occ_vec = np.zeros(D, dtype=np.float64)
    bitmasks = [sum(1 << p for p in c) for c in up_configs]
    for u_i, bm_u in enumerate(bitmasks):
        base = u_i * n_single
        for d_i, bm_d in enumerate(bitmasks):
            double_occ_vec[base + d_i] = float((bm_u & bm_d).bit_count())

    diag_U = u_on * double_occ_vec

    def matvec(psi: np.ndarray) -> np.ndarray:
        # Acción Kronecker exacta O(D * n_single) sin instanciar matriz 3136 x 3136:
        # (T_spin (x) I + I (x) T_spin^T) vec(Psi) = T_spin @ Psi + Psi @ T_spin^T
        Psi_mat = psi.reshape(n_single, n_single)
        kin = (T_spin @ Psi_mat) + (Psi_mat @ T_spin.T)
        return kin.ravel() + diag_U * psi

    return matvec, up_configs, double_occ_vec, D


def compute_exact_singlet_pairing(psi: np.ndarray, up_configs, bonds) -> dict:
    """
    Calcula exactamente sobre |psi> (sector 3 up, 3 dn -> sector intermedio 2 up, 2 dn de dim 28x28=784)
    las correlaciones de apareamiento singlete:
      Delta_{ij} = (c_{i,up} c_{j,dn} + c_{j,up} c_{i,dn}) / sqrt(2)
      P_alpha = (1 / N_b) * || sum_b f_alpha(b) Delta_b |psi> ||_2^2
    También separa la contribución de largo alcance (enlaces que NO comparten vértice)
    para eliminar la auto-correlación trivial de un mismo enlace b == b'.
    """
    n_single_3 = len(up_configs)  # 56
    configs_2 = list(itertools.combinations(range(8), 2))  # 28
    n_single_2 = len(configs_2)
    map_2 = {conf: idx for idx, conf in enumerate(configs_2)}
    dim_22 = n_single_2 * n_single_2  # 784

    # Precalcular acción de c_{p} desde configs de 3 partículas -> configs de 2 partículas
    ann_table = {}
    for p in range(8):
        src_list = []
        dst_list = []
        sgn_list = []
        for idx3, conf3 in enumerate(up_configs):
            if p in conf3:
                pos = conf3.index(p)
                sgn = -1.0 if (pos % 2 == 1) else 1.0
                conf2 = tuple(x for x in conf3 if x != p)
                src_list.append(idx3)
                dst_list.append(map_2[conf2])
                sgn_list.append(sgn)
        ann_table[p] = (
            np.array(src_list, dtype=np.int32),
            np.array(dst_list, dtype=np.int32),
            np.array(sgn_list, dtype=np.float64),
        )

    Psi_mat = psi.reshape(n_single_3, n_single_3)
    inv_sqrt2 = 1.0 / math.sqrt(2.0)

    bond_vectors = []
    for i, j, f_d in bonds:
        # En el orden |u>|d>, c_{i,up} c_{j,dn} |u,d> = (-1)^{N_up} (c_{i,up}|u>) (c_{j,dn}|d>)
        # Para N_up = 3 fijo, (-1)^3 = -1 global en todos los términos singlete.
        u_src_i, u_dst_i, u_sgn_i = ann_table[i]
        d_src_j, d_dst_j, d_sgn_j = ann_table[j]

        u_src_j, u_dst_j, u_sgn_j = ann_table[j]
        d_src_i, d_dst_i, d_sgn_i = ann_table[i]

        vec_22 = np.zeros((n_single_2, n_single_2), dtype=np.float64)
        # Término 1: c_{i,up} c_{j,dn}
        sub1 = Psi_mat[np.ix_(u_src_i, d_src_j)] * np.outer(u_sgn_i, d_sgn_j)
        vec_22[np.ix_(u_dst_i, d_dst_j)] -= inv_sqrt2 * sub1
        # Término 2: + c_{j,up} c_{i,dn} (singlete de espín S=0)
        sub2 = Psi_mat[np.ix_(u_src_j, d_src_i)] * np.outer(u_sgn_j, d_sgn_i)
        vec_22[np.ix_(u_dst_j, d_dst_i)] -= inv_sqrt2 * sub2

        bond_vectors.append((i, j, f_d, vec_22.ravel()))

    n_bonds = len(bonds)
    # Matriz de correlación de pares M_{b, b'} = <psi | Delta_b^dagger Delta_{b'} | psi>
    M_pair = np.zeros((n_bonds, n_bonds), dtype=np.float64)
    for b1 in range(n_bonds):
        for b2 in range(b1, n_bonds):
            val = float(np.dot(bond_vectors[b1][3], bond_vectors[b2][3]))
            M_pair[b1, b2] = val
            M_pair[b2, b1] = val

    f_d_vec = np.array([b[2] for b in bonds], dtype=np.float64)
    f_s_vec = np.ones(n_bonds, dtype=np.float64)

    P_d_total = float(f_d_vec @ M_pair @ f_d_vec) / n_bonds
    P_s_total = float(f_s_vec @ M_pair @ f_s_vec) / n_bonds

    # Correlación no-local estricta (pares de enlaces disjuntos que NO comparten sitios)
    P_d_nonlocal = 0.0
    P_s_nonlocal = 0.0
    n_disjoint_pairs = 0
    for b1 in range(n_bonds):
        s_a = {bonds[b1][0], bonds[b1][1]}
        for b2 in range(n_bonds):
            s_b = {bonds[b2][0], bonds[b2][1]}
            if s_a.isdisjoint(s_b):
                n_disjoint_pairs += 1
                P_d_nonlocal += f_d_vec[b1] * f_d_vec[b2] * M_pair[b1, b2]
                P_s_nonlocal += f_s_vec[b1] * f_s_vec[b2] * M_pair[b1, b2]
    P_d_nonlocal /= n_bonds
    P_s_nonlocal /= n_bonds

    return {
        "P_d_total": P_d_total,
        "P_s_total": P_s_total,
        "P_d_nonlocal": P_d_nonlocal,
        "P_s_nonlocal": P_s_nonlocal,
        "disjoint_bond_pairs": n_disjoint_pairs,
    }


def main():
    t0 = time.perf_counter()
    print("=" * 80)
    print("POLYDIM / EINSOF — 2D HUBBARD CLUSTER (BETTS 8-SITE): EXACT PAIRING SOLVER")
    print("[NOTA HONESTIDAD RADICAL]: Simulación exacta de clúster finito en CPU local (D=3,136).")
    print("=" * 80)

    bonds = build_betts_sqrt8_cluster()
    # Resolver U/t = 6.0 (interactuante) y U/t = 0.0 (gas libre de referencia para medir vértice intrínseco)
    matvec_u6, up_configs, double_occ_vec, D = build_hubbard_8site_operator(bonds, t_hop=1.0, u_on=6.0)
    res_u6 = stiefel_lanczos_ground_state(matvec_u6, D, max_krylov=90, tol=1e-12, seed=1986)

    matvec_u0, _, _, _ = build_hubbard_8site_operator(bonds, t_hop=1.0, u_on=0.0)
    res_u0 = stiefel_lanczos_ground_state(matvec_u0, D, max_krylov=90, tol=1e-12, seed=1986)

    psi = res_u6["psi"]
    e0 = res_u6["energy"]
    d_occ = float(np.dot(psi * psi, double_occ_vec)) / 8.0

    pair_u6 = compute_exact_singlet_pairing(psi, up_configs, bonds)
    pair_u0 = compute_exact_singlet_pairing(res_u0["psi"], up_configs, bonds)

    # Susceptibilidad / vértice intrínseco respecto a U=0: Delta_P = P(U=6) - P(U=0)
    vertex_d_nonlocal = pair_u6["P_d_nonlocal"] - pair_u0["P_d_nonlocal"]
    vertex_s_nonlocal = pair_u6["P_s_nonlocal"] - pair_u0["P_s_nonlocal"]
    ratio_total = pair_u6["P_d_total"] / max(pair_u6["P_s_total"], 1e-15)

    t_total_ms = (time.perf_counter() - t0) * 1000.0

    print(f"[1] Estado Base Convergido (U/t=6.0, D={D}):")
    print(f"    -> Energía E_0:                  {e0:.10f} t ({e0/8.0:.8f} t/sitio)")
    print(f"    -> Residuo ||H psi - E_0 psi||:  {res_u6['residual_norm']:.3e} (Hermiticidad: {res_u6['hermiticity_defect']:.2e})")
    print(f"    -> Deriva Neumaier en S^3135:    {res_u6['stiefel_state_drift']:.2e} | Matvecs: {res_u6['matvecs']}")
    print(f"    -> Doble Ocupación <n_up n_dn>:  {d_occ:.6f} (vs { (3/8)*(3/8):.6f} libre)")

    print(f"\n[2] Correlaciones Cuánticas Reales Calculadas desde |psi_0> (CERO hardcodeo):")
    print(f"    -> P_d (total estructura par):   {pair_u6['P_d_total']:.6f}  | P_s (extendida s): {pair_u6['P_s_total']:.6f} (Ratio d/s = {ratio_total:.3f}x)")
    print(f"    -> P_d (enlaces disjuntos):      {pair_u6['P_d_nonlocal']:+.6f} | P_s (disjuntos):   {pair_u6['P_s_nonlocal']:+.6f}")
    print(f"    -> Vértice P(U=6) - P(U=0) disj: d-wave = {vertex_d_nonlocal:+.6f} | s-wave = {vertex_s_nonlocal:+.6f}")

    output_data = {
        "scope_disclaimer": "Exact diagonalization on finite 8-site sqrt(8)xsqrt(8) Betts CPU cluster; NOT a thermodynamic-limit proof.",
        "problem": "2D_REPULSIVE_HUBBARD_8SITE_BETTS_PAIRING",
        "n_sites": 8,
        "n_electrons": 6,
        "doping_delta": 0.25,
        "U_over_t": 6.0,
        "hilbert_dim": D,
        "ground_energy_t": round(e0, 10),
        "ground_energy_per_site": round(e0 / 8.0, 10),
        "eigenstate_residual_norm": res_u6["residual_norm"],
        "hermiticity_defect": res_u6["hermiticity_defect"],
        "double_occupancy": round(d_occ, 6),
        "p_dwave_total": round(pair_u6["P_d_total"], 6),
        "p_swave_total": round(pair_u6["P_s_total"], 6),
        "p_dwave_nonlocal_disjoint": round(pair_u6["P_d_nonlocal"], 6),
        "p_swave_nonlocal_disjoint": round(pair_u6["P_s_nonlocal"], 6),
        "pairing_ratio_d_over_s": round(ratio_total, 4),
        "neumaier_drift": res_u6["stiefel_state_drift"],
        "execution_ms": round(t_total_ms, 2),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    data_dir = "E:/POLYDIM_EINSOF/quantum/data"
    os.makedirs(data_dir, exist_ok=True)
    data_path = os.path.join(data_dir, "cuprate_dwave_superconductivity.json")
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\n[3] Datos reales guardados en: {data_path}")

    bus = PersistentMmapSlabBus()
    slab_id = 0x504D3136
    meta_slab = bus.write_tensor_slab(slab_id, psi)
    print(f"[4] PMTP Slab actualizado: {meta_slab['slab_id_hex']} ({meta_slab['dim'] * 8} bytes)")

    conn = psycopg2.connect("dbname=polydim_vec_db user=postgres password=postgres host=localhost port=5432")
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO session_context (conversation_id, summary, category, created_at)
        VALUES (%s, %s, %s, NOW())
        RETURNING id;
        """,
        ("3f34edfc-4b9c-4658-84fc-10d32ef4da9b", json.dumps(output_data, ensure_ascii=False), "REPAIRED_2D_HUBBARD_EXACT_PAIRING"),
    )
    row_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    print(f"[5] Persistido en PostgreSQL 16 (DB_ID: {row_id}) | Latencia: {t_total_ms:.1f} ms | EXIT CODE 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
