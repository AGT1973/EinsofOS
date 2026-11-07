"""
ESCALAMIENTO DE ENTRELAZAMIENTO GHZ EN IBM QUANTUM:
MAPA DE DECOHERENCIA vs NÚMERO DE QUBITS (3 a 20)
===================================================
Prepara estados GHZ genuinos de N qubits en QPU física y mide:
1. Fidelidad diagonal: P(|0...0⟩) + P(|1...1⟩) (medición en base Z)
2. Coherencia off-diagonal: ⟨X^⊗N⟩ (medición en base X)
3. Cota inferior de fidelidad GHZ: F_GHZ >= (F_diag + ⟨X^⊗N⟩) / 2

Si F_GHZ > 0.5, el estado tiene entrelazamiento genuino.
A medida que N crece, el ruido del chip destruye progresivamente
la coherencia cuántica. Esto mapea la frontera real del hardware.

Todos los Job IDs son verificables en: https://quantum.ibm.com/jobs/<JOB_ID>

Referencia: Sackett et al. (2000) Nature 404, 256;
            Gühne & Tóth (2009) Physics Reports 474, 1-75.

Autor: Ariel García Traba (Independent Research / EinsofOS)
"""

import time
import json
import numpy as np
from qiskit import QuantumCircuit
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
import psycopg2


def get_ibm_token():
    conn = psycopg2.connect(
        dbname='polydim_active_db', user='postgres',
        password='postgres', host='localhost', port=5432
    )
    cur = conn.cursor()
    cur.execute("SELECT value FROM active_vault WHERE key_name = 'ibm_quantum_api_key'")
    token = cur.fetchone()[0]
    cur.close()
    conn.close()
    return token


def create_ghz_z_measure(n):
    """GHZ state + measure in Z basis (diagonal fidelity)."""
    qc = QuantumCircuit(n)
    qc.h(0)
    for i in range(1, n):
        qc.cx(0, i)
    qc.measure_all()
    return qc


def create_ghz_x_measure(n):
    """GHZ state + measure in X basis (coherence witness)."""
    qc = QuantumCircuit(n)
    qc.h(0)
    for i in range(1, n):
        qc.cx(0, i)
    qc.barrier()
    # Rotate all qubits to X basis
    for i in range(n):
        qc.h(i)
    qc.measure_all()
    return qc


def compute_parity_expectation(counts):
    """Compute ⟨(-1)^parity⟩ from measurement counts."""
    total = sum(counts.values())
    if total == 0:
        return 0.0
    val = 0.0
    for bitstring, count in counts.items():
        bits = bitstring.replace(' ', '')
        parity = bits.count('1') % 2
        val += count * ((-1) ** parity)
    return val / total


def compute_ghz_diagonal_fidelity(counts, n):
    """Compute P(|0...0⟩) + P(|1...1⟩) from Z-basis measurement."""
    total = sum(counts.values())
    if total == 0:
        return 0.0
    all_zeros = '0' * n
    all_ones = '1' * n
    p_zeros = counts.get(all_zeros, 0) / total
    p_ones = counts.get(all_ones, 0) / total
    return p_zeros + p_ones


def main():
    t0 = time.perf_counter()

    qubit_counts = [3, 5, 8, 12, 16, 20]
    shots = 4000

    print("=" * 70)
    print("ESCALAMIENTO GHZ EN IBM QUANTUM: MAPA DE DECOHERENCIA")
    print("=" * 70)
    print(f"Qubits a probar: {qubit_counts}")
    print(f"Shots por circuito: {shots}")
    print(f"Circuitos por N: 2 (base Z + base X)")
    print(f"Total circuitos: {len(qubit_counts) * 2}")

    # 1. Connect to IBM
    token = get_ibm_token()
    print("\n[1/4] Conectando a IBM Quantum Platform...")
    service = QiskitRuntimeService(
        channel="ibm_quantum_platform",
        token=token,
        instance="open-instance"
    )

    backend_name = "ibm_marrakesh"
    backend = service.backend(backend_name)
    status = backend.status()
    print(f"       Backend: {backend_name} ({backend.num_qubits}Q)")
    print(f"       operational={status.operational}, pending_jobs={status.pending_jobs}")

    # 2. Create all circuits
    print("\n[2/4] Creando circuitos GHZ + medición para cada N...")
    all_circuits = []
    circuit_map = []  # (n_qubits, basis_type, index_in_all)

    for n in qubit_counts:
        # Z-basis circuit
        qc_z = create_ghz_z_measure(n)
        all_circuits.append(qc_z)
        circuit_map.append((n, 'Z', len(all_circuits) - 1))

        # X-basis circuit
        qc_x = create_ghz_x_measure(n)
        all_circuits.append(qc_x)
        circuit_map.append((n, 'X', len(all_circuits) - 1))

        print(f"    GHZ({n:2d}): Z-basis y X-basis creados")

    # 3. Transpile for hardware
    print("\n[3/4] Transpilando para topología física del chip...")
    pm = generate_preset_pass_manager(optimization_level=3, backend=backend)
    transpiled = pm.run(all_circuits)

    for entry in circuit_map:
        n, basis, idx = entry
        tc = transpiled[idx]
        ops = tc.count_ops()
        two_q = sum(v for k, v in ops.items() if k in ['ecr', 'cx', 'cz', 'rzz'])
        print(f"    GHZ({n:2d}) base {basis}: depth={tc.depth()}, "
              f"2Q_gates={two_q}, total_gates={sum(ops.values())}")

    # 4. Submit to QPU
    print(f"\n[4/4] Enviando {len(transpiled)} circuitos al QPU real...")
    sampler = SamplerV2(mode=backend)
    pubs = [(tc,) for tc in transpiled]
    job = sampler.run(pubs, shots=shots)
    job_id = job.job_id()
    ibm_url = f"https://quantum.ibm.com/jobs/{job_id}"

    print(f"       Job ID:  {job_id}")
    print(f"       URL IBM: {ibm_url}")
    print(f"       Esperando resultados del QPU físico...")

    result = job.result()
    t_qpu = time.perf_counter()
    print(f"       ¡Resultados recibidos! ({t_qpu - t0:.1f} segundos)")

    # 5. Analyze results
    print("\n" + "=" * 70)
    print("RESULTADOS FÍSICOS: FIDELIDAD GHZ vs NÚMERO DE QUBITS")
    print("=" * 70)
    print(f"{'N':>4} | {'F_diag':>8} | {'⟨X^N⟩':>8} | {'F_GHZ':>8} | {'Entrelaz.':>10} | {'Ruido':>8}")
    print("-" * 70)

    results_table = []
    previous_job_ids = {
        3: "dbm99558ft8s738ueesg"  # Mermin experiment from before
    }

    for n in qubit_counts:
        # Find the Z and X results for this N
        z_idx = None
        x_idx = None
        for entry in circuit_map:
            if entry[0] == n and entry[1] == 'Z':
                z_idx = entry[2]
            elif entry[0] == n and entry[1] == 'X':
                x_idx = entry[2]

        # Z-basis: diagonal fidelity
        z_counts = result[z_idx].data.meas.get_counts()
        f_diag = compute_ghz_diagonal_fidelity(z_counts, n)

        # X-basis: coherence (parity expectation)
        x_counts = result[x_idx].data.meas.get_counts()
        x_parity = compute_parity_expectation(x_counts)

        # GHZ fidelity lower bound
        f_ghz = (f_diag + x_parity) / 2.0
        entangled = f_ghz > 0.5
        noise_pct = (1.0 - f_ghz) * 100.0

        # Top bitstrings for Z measurement
        z_top = dict(sorted(z_counts.items(), key=lambda x: -x[1])[:4])

        status_str = "SÍ ✓" if entangled else "NO ✗"
        print(f"{n:4d} | {f_diag:8.4f} | {x_parity:+8.4f} | {f_ghz:8.4f} | {status_str:>10} | {noise_pct:7.2f}%")

        row = {
            "n_qubits": n,
            "f_diagonal": round(float(f_diag), 6),
            "x_parity": round(float(x_parity), 6),
            "f_ghz_lower_bound": round(float(f_ghz), 6),
            "entanglement_detected": entangled,
            "noise_percentage": round(float(noise_pct), 2),
            "z_basis_top_bitstrings": z_top,
            "total_shots": sum(z_counts.values())
        }
        results_table.append(row)

    t1 = time.perf_counter()

    # Final report
    report = {
        "experiment_type": "REAL_QUANTUM_PHYSICS_MEASUREMENT",
        "title": "GHZ Entanglement Scaling & Decoherence Map on IBM Quantum",
        "references": [
            "Mermin, N.D. (1990) PRL 65, 1838",
            "Sackett et al. (2000) Nature 404, 256",
            "Gühne & Tóth (2009) Physics Reports 474, 1-75"
        ],
        "backend": {
            "name": backend_name,
            "total_qubits": backend.num_qubits,
            "operational": True
        },
        "verification": {
            "scaling_job_id": job_id,
            "scaling_job_url": ibm_url,
            "previous_mermin_3q_job_id": "dbm99558ft8s738ueesg",
            "previous_mermin_3q_job_url": "https://quantum.ibm.com/jobs/dbm99558ft8s738ueesg",
            "ibm_dashboard": "https://quantum.ibm.com",
            "note": "Todos los Job IDs son verificables en el panel de IBM Quantum con las credenciales de la cuenta."
        },
        "parameters": {
            "qubit_counts_tested": qubit_counts,
            "shots_per_circuit": shots,
            "total_circuits": len(all_circuits),
            "optimization_level": 3
        },
        "results": results_table,
        "total_experiment_time_seconds": round(t1 - t0, 2)
    }

    # Persist to PostgreSQL
    try:
        conn = psycopg2.connect(
            dbname='polydim_vec_db', user='postgres',
            password='postgres', host='localhost', port=5432
        )
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO session_context (conversation_id, summary, category, created_at)
            VALUES (%s, %s, %s, NOW())
        """, ('a9c79c56-9fe9-42ad-bb67-80d40e88c44e',
              json.dumps(report), 'REAL_QPU_GHZ_SCALING_DECOHERENCE_MAP'))
        conn.commit()
        cur.close()
        conn.close()
        print("\n[DB] Persistido en PostgreSQL 16 (session_context).")
    except Exception as e:
        print(f"\n[DB WARN] Error al persistir: {e}")

    print("\n=== LINKS DE VERIFICACIÓN EN IBM QUANTUM ===")
    print(f"Mermin 3Q (anterior):  https://quantum.ibm.com/jobs/dbm99558ft8s738ueesg")
    print(f"Escalamiento GHZ:      {ibm_url}")
    print(f"Dashboard IBM:         https://quantum.ibm.com")

    print("\n=== REPORTE FINAL ===")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    main()
