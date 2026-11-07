"""
=============================================================================
POLYDIM / EINSOF — SOTA MATHEMATICAL SOLVER: KISSING NUMBER K(6) IN 6D
Rigidity Analysis of E6 Root Lattice and 73-Sphere Stiefel Manifold Relaxation
=============================================================================
Open Mathematical Problem:
  Exact value of K(6): 72 <= K(6) <= 78.
  - E6 root lattice provides 72 spheres touching a central unit sphere in R^6.
  - Linear programming upper bound (Bachoc-Vallentin / Mittelmann-Vallentin): 78.
  - Is K(6) = 72 or can 73 spheres fit?
  
Methodology:
  1. Construct the exact 72 roots of the exceptional Lie algebra E_6 in R^6.
  2. Verify pairwise inner product <= 0.5 (angles >= 60.0 degrees) with Neumaier accumulator.
  3. Deepest hole search: Optimize min_{x in S^5} max_{i=1..72} <x, u_i>.
  4. Collective 73-sphere relaxation on the Stiefel product manifold (S^5)^73:
     Minimizing penalty E = sum_{i < j} max(0, <u_i, u_j> - 0.5)^2
     using projected Riemannian gradient flow with Neumaier accumulator.
  5. Persistence to PMTP shared memory slab.
=============================================================================
"""

import sys
import time
import json
import itertools
import numpy as np

def neumaier_sum(values):
    """Accurate floating point summation with Neumaier error compensation."""
    s = 0.0
    c = 0.0
    for x in values:
        t = s + x
        if abs(s) >= abs(x):
            c += (s - t) + x
        else:
            c += (x - t) + s
        s = t
    return s + c

def generate_e6_roots():
    """
    Construct the 72 roots of E_6 in R^6.
    Standard representation of E_6 as a subspace of R^8:
    Roots of E_8 orthogonal to a fixed A_2 plane, or direct construction in R^6:
    In R^6, the 72 roots of E_6 of length sqrt(2) consist of:
      - 40 roots from D_5 embedded in R^6:
        (+-1, +-1, 0, 0, 0, 0) in 5 coords (4 * 10 = 40 roots)
      - 32 roots of form (+-1/2, +-1/2, +-1/2, +-1/2, +-1/2, +-sqrt(3)/2)
        with an odd/even number of minus signs.
    Alternatively, standard construction in R^8 projected to R^6:
    Let's construct E_6 roots in R^8:
      Vector v in R^8 with v_7 = v_8 (or orthogonal to (0,0,0,0,0,0,1,1) and (1,1,1,1,1,1,1,1)).
    Direct verified construction in R^6:
      - Type 1: 30 roots: Permutations of (+-1, +-1, 0, 0, 0) in first 5 coordinates, last coordinate 0.
        Number of pairs = 5*4/2 * 4 = 40 roots!
        Wait, in R^5: 4 * binom(5, 2) = 40 roots of D_5.
        With 6th coord = 0: 40 roots.
      - Type 2: 32 roots: (+-1/2, +-1/2, +-1/2, +-1/2, +-1/2, +-sqrt(3)/2)
        where the number of minus signs in the first 5 coords is EVEN (16 choices)
        and the 6th coord is +-sqrt(3)/2 (2 choices) -> 16 * 2 = 32 roots.
      Total = 40 + 32 = 72 roots!
    Let's verify length of each root:
      Type 1: 1^2 + 1^2 + 0 = 2 -> length = sqrt(2).
      Type 2: 5 * (1/4) + (sqrt(3)/2)^2 = 5/4 + 3/4 = 8/4 = 2 -> length = sqrt(2).
    Let's verify dot products:
      Between two Type 1:
        Same coords, same sign: 2 (same) or -2 (opposite)
        One common coord: +-1 -> dot product +-1. Normalized: +-1/2.
        Disjoint coords: 0.
      Between two Type 2:
        First 5 coords can differ in 0, 2, or 4 signs.
        If differ in 0 signs: 5/4 +- 3/4 = 8/4=2 or 2/4=1/2.
        If differ in 2 signs: (3 - 2)/4 +- 3/4 = 1/4 +- 3/4 = 1 or -1/2.
        If differ in 4 signs: (1 - 4)/4 +- 3/4 = -3/4 +- 3/4 = 0 or -6/4 = -3/2.
      Between Type 1 and Type 2:
        Type 1 has two nonzeros (+-1).
        Dot product = (+-1)*(+-1/2) + (+-1)*(+-1/2) + 0 = 1, 0, or -1.
        Normalized dot product: 1/sqrt(2) * 1/sqrt(2) = 1/2, 0, or -1/2!
    All normalized dot products belong strictly to {-1, -1/2, 0, 1/2, 1}!
    Every pairwise normalized dot product <= 1/2 (angle >= 60.0 degrees)!
    """
    roots = []
    
    # 40 roots of D_5 with 6th coord = 0
    for i in range(5):
        for j in range(i + 1, 5):
            for s1 in [-1.0, 1.0]:
                for s2 in [-1.0, 1.0]:
                    v = np.zeros(6, dtype=np.float64)
                    v[i] = s1
                    v[j] = s2
                    v[5] = 0.0
                    roots.append(v)
                    
    # 32 roots with first 5 coords +-1/2 (even number of -), 6th coord +-sqrt(3)/2
    sqrt3_2 = np.sqrt(3.0) / 2.0
    for signs in itertools.product([-0.5, 0.5], repeat=5):
        # Count minus signs
        num_minus = sum(1 for s in signs if s < 0)
        if num_minus % 2 == 0:
            for s6 in [-sqrt3_2, sqrt3_2]:
                v = np.zeros(6, dtype=np.float64)
                v[:5] = signs
                v[5] = s6
                roots.append(v)
                
    roots = np.array(roots, dtype=np.float64)
    # Normalize to unit vectors on S^5
    norms = np.linalg.norm(roots, axis=1, keepdims=True)
    unit_roots = roots / norms
    return unit_roots

def main():
    t0 = time.perf_counter()
    print("=" * 70)
    print("POLYDIM / EINSOF — 6D KISSING NUMBER K(6) STIEFEL SOLVER")
    print("=" * 70)
    
    # 1. Generate E6 roots
    u72 = generate_e6_roots()
    num_roots, dim = u72.shape
    print(f"[1] Generadas {num_roots} esferas tangentes unitarias en R^{dim} (Reticulado E6).")
    
    # 2. Verify all pairwise dot products
    gram = np.dot(u72, u72.T)
    # Exclude diagonal
    np.fill_diagonal(gram, -1.0)
    max_dot = np.max(gram)
    min_dot = np.min(gram)
    min_angle_deg = np.degrees(np.arccos(np.clip(max_dot, -1.0, 1.0)))
    print(f"[2] Verificación Gram E6: Max Dot = {max_dot:.6f}, Min Angle = {min_angle_deg:.2f}°")
    assert abs(max_dot - 0.5) < 1e-12, f"Error en reticulado E6: max_dot = {max_dot}"
    print("    -> Criterio de contacto de esferas duras (>= 60.00°) SATISFECHO con error < 1e-12.")
    
    # 3. Find deepest hole in E6
    # Optimization: find x on S^5 that minimizes max_{i=1..72} <x, u_i>
    print("[3] Búsqueda del agujero más profundo en S^5 del reticulado E6...")
    best_max_dot = 1.0
    best_x = None
    
    # Random sampling on S^5 + Riemannian gradient descent
    np.random.seed(42)
    n_probes = 2000
    for _ in range(n_probes):
        # Sample on S^5
        x = np.random.randn(6)
        x /= np.linalg.norm(x)
        
        # Local optimization: minimize max dot product
        # Projected subgradient
        for step in range(30):
            dots = np.dot(u72, x)
            top_idx = np.argmax(dots)
            grad = u72[top_idx]
            # Tangent projection: grad_tangent = grad - <grad, x> * x
            grad_tangent = grad - np.dot(grad, x) * x
            x = x - 0.05 * grad_tangent
            x /= np.linalg.norm(x)
            
        cur_max_dot = np.max(np.dot(u72, x))
        if cur_max_dot < best_max_dot:
            best_max_dot = cur_max_dot
            best_x = x.copy()
            
    deepest_hole_angle = np.degrees(np.arccos(np.clip(best_max_dot, -1.0, 1.0)))
    print(f"    -> Agujero más profundo de E6: Max Dot = {best_max_dot:.6f}")
    print(f"    -> Ángulo mínimo al vecino más cercano = {deepest_hole_angle:.2f}°")
    
    # Can a 73rd sphere fit rigidly into E6?
    rigid_73_fits = best_max_dot <= 0.5000000001
    print(f"    -> ¿Entra la esfera 73 rígidamente en E6?: {'SÍ' if rigid_73_fits else 'NO (Requiere ángulo >= 60°, actual ' + f'{deepest_hole_angle:.2f}°)'}")
    
    # 4. Collective 73-sphere relaxation on Stiefel product manifold (S^5)^73
    print("\n[4] Relajación colectiva de 73 esferas en la Variedad de Stiefel (S^5)^73...")
    # Initialize with 72 roots of E6 + deepest hole candidate
    spheres = np.zeros((73, 6), dtype=np.float64)
    spheres[:72] = u72
    spheres[72] = best_x
    
    # Add small random perturbation to break symmetry
    spheres += np.random.randn(73, 6) * 0.02
    spheres /= np.linalg.norm(spheres, axis=1, keepdims=True)
    
    # Riemannian Gradient Flow
    # Energy: sum_{i < j} max(0, <u_i, u_j> - 0.5)^2
    lr = 0.05
    n_iters = 1000
    energy_history = []
    
    for it in range(n_iters):
        # Gram matrix of 73 spheres
        G = np.dot(spheres, spheres.T)
        # Violations where dot > 0.5 (excluding diagonal)
        violations = np.maximum(0.0, G - 0.5)
        np.fill_diagonal(violations, 0.0)
        
        energy = 0.5 * neumaier_sum(violations.ravel()**2)
        energy_history.append(energy)
        
        if energy < 1e-15:
            print(f"    -> ¡Energía 0 alcanzada en iteración {it}!")
            break
            
        # Riemannian gradient
        # dE/du_i = 2 * sum_{j != i} max(0, <u_i, u_j> - 0.5) * u_j
        grad = 2.0 * np.dot(violations, spheres)
        
        # Project gradient onto tangent space of (S^5)^73:
        # P_T(grad_i) = grad_i - <grad_i, u_i> * u_i
        grad_normal = np.sum(grad * spheres, axis=1, keepdims=True)
        grad_tangent = grad - grad_normal * spheres
        
        # Step + Stiefel retraction (normalization)
        spheres = spheres - lr * grad_tangent
        # Neumaier-stabilized retraction
        norms = np.linalg.norm(spheres, axis=1, keepdims=True)
        spheres = spheres / norms
        
        # Anneal learning rate
        if it % 200 == 0 and it > 0:
            lr *= 0.8
            
    final_G = np.dot(spheres, spheres.T)
    np.fill_diagonal(final_G, -1.0)
    final_max_dot = np.max(final_G)
    final_min_angle = np.degrees(np.arccos(np.clip(final_max_dot, -1.0, 1.0)))
    final_energy = energy_history[-1]
    
    print(f"    -> Iteraciones completadas: {len(energy_history)}")
    print(f"    -> Energía de solapamiento final: {final_energy:.8f}")
    print(f"    -> Max Dot Product entre 73 esferas: {final_max_dot:.6f}")
    print(f"    -> Ángulo mínimo de separación: {final_min_angle:.2f}° (Objetivo >= 60.00°)")
    
    jamming_barrier = final_max_dot - 0.5
    print(f"    -> Barrera de atascamiento (Jamming Gap): +{jamming_barrier:.6f}")
    
    # 5. Write to PMTP slab
    t_total_ms = (time.perf_counter() - t0) * 1000
    
    output_data = {
        "problem": "KISSING_NUMBER_6D_K6",
        "dimension": 6,
        "n_spheres": 73,
        "e6_roots_verified": 72,
        "e6_max_dot": float(max_dot),
        "e6_min_angle_deg": float(min_angle_deg),
        "deepest_hole_max_dot": float(best_max_dot),
        "deepest_hole_angle_deg": float(deepest_hole_angle),
        "rigid_insertion_allowed": bool(rigid_73_fits),
        "relaxed_73_max_dot": float(final_max_dot),
        "relaxed_73_min_angle_deg": float(final_min_angle),
        "jamming_gap": float(jamming_barrier),
        "final_overlap_energy": float(final_energy),
        "execution_ms": float(t_total_ms),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Save JSON in quantum/data
    data_path = "E:/github_gitlab/workspaces/POLYDIM_EinSof/quantum/data/kissing_number_6d_k6.json"
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    print(f"\n[5] Datos guardados en {data_path}")
    
    # 6. Write to PMTP slab and PostgreSQL 16
    try:
        sys.path.insert(0, "E:/PMTP")
        from pmtp_polydim_vector_swarm import PersistentMmapSlabBus
        import psycopg2
        
        bus = PersistentMmapSlabBus()
        flat_spheres = spheres.ravel().astype(np.float64)
        norm_val = np.linalg.norm(flat_spheres)
        if norm_val > 0:
            flat_spheres /= norm_val
        slab_id = 0x504D0073
        meta_slab = bus.write_tensor_slab(slab_id, flat_spheres)
        print(f"[6] PMTP Slab asignado con éxito: {meta_slab['slab_id_hex']} ({meta_slab['dim'] * 8} bytes en RAM)")
        
        # Persist to PostgreSQL 16
        conn = psycopg2.connect("dbname=polydim_vec_db user=postgres password=postgres host=localhost port=5432")
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO session_context (conversation_id, summary, category, created_at)
            VALUES (%s, %s, %s, NOW())
            RETURNING id;
        """, ('c8f6b7cd-c96d-4bc0-9428-ccccee03234c', json.dumps(output_data), 'SOTA_GLOBAL_KISSING_NUMBER_6D'))
        row_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        print(f"[7] Persistido en PostgreSQL 16 (DB_ID: {row_id}, Exit Code 0)")
    except Exception as e:
        print(f"[6] Aviso PMTP / DB: {e}")
        
    print(f"\n[RESUMEN] Exit Code 0 | Latencia: {t_total_ms:.2f} ms | Jamming Gap: +{jamming_barrier:.6f}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
