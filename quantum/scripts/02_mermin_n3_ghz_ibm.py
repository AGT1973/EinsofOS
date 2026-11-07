"""
EXPERIMENTO REAL: VIOLACIÓN DE LA DESIGUALDAD DE MERMIN EN IBM QUANTUM
======================================================================
Preparación de estado GHZ genuino en QPU física y verificación de
entrelazamiento cuántico mediante la desigualdad de Mermin.

Este es un experimento de FÍSICA CUÁNTICA FUNDAMENTAL que solo puede
realizarse en hardware cuántico real. Ninguna simulación clásica
constituye una medición física genuina de entrelazamiento.

Desigualdad de Mermin para 3 qubits:
   M_3 = ⟨XXX⟩ - ⟨XYY⟩ - ⟨YXY⟩ - ⟨YYX⟩
   Cota clásica (teorías de variable oculta local): |M_3| ≤ 2
   Valor cuántico ideal (estado GHZ):              |M_3| = 4

Si el QPU mide M_3 > 2, se demuestra entrelazamiento genuino
tripartito que NO puede ser explicado por ninguna teoría clásica.

Referencia: Mermin, N.D. (1990) "Extreme quantum entanglement in a
superposition of macroscopically distinct states" PRL 65, 1838.

Autor: Ariel García Traba (Independent Research / EinsofOS)
"""

import time
import json
import numpy as np
from qiskit import QuantumCircuit
from qiskit.primitives import StatevectorSampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
import psycopg2


def get_ibm_token():
    """Lee el token de IBM desde PostgreSQL 16 (active_vault)."""
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


def create_ghz_and_measure(n_qubits, bases):
    """
    Crea un circuito que:
    1. Prepara el estado GHZ: (|00...0⟩ + |11...1⟩) / √2
    2. Rota a la base de medición indicada (X, Y o Z por qubit)
    3. Mide todos los qubits

    Bases de medición:
    - 'X': aplicar H antes de medir (eigenstates de X -> Z)
    - 'Y': aplicar Sdg + H antes de medir (eigenstates de Y -> Z)
    - 'Z': medir directo (sin rotación)
    """
    qc = QuantumCircuit(n_qubits)

    # Paso 1: Preparar GHZ
    qc.h(0)
    for i in range(1, n_qubits):
        qc.cx(0, i)

    qc.barrier()

    # Paso 2: Rotar a la base de medición
    for q, basis in enumerate(bases):
        if basis == 'X':
            qc.h(q)
        elif basis == 'Y':
            qc.sdg(q)
            qc.h(q)
        # 'Z': no se aplica nada

    # Paso 3: Medir
    qc.measure_all()
    return qc


def compute_correlator(counts, n_qubits):
    """
    Calcula el valor del correlador ⟨O_1 O_2 ... O_N⟩ a partir de
    las cuentas de medición.

    Cada bit b_i se mapea al eigenvalue (-1)^b_i.
    El correlador es el promedio de (-1)^(paridad del bitstring).
    """
    total = sum(counts.values())
    if total == 0:
        return 0.0

    expectation = 0.0
    for bitstring, count in counts.items():
        bits = bitstring.replace(' ', '')
        parity = bits.count('1') % 2
        expectation += count * ((-1) ** parity)

    return expectation / total


def run_ideal_simulation(n_qubits, shots):
    """Ejecuta la simulación ideal (sin ruido) como referencia."""
    print(f"\n--- Simulación ideal (sin ruido, {shots} shots) ---")

    mermin_bases = [
        ('X', 'X', 'X'),
        ('X', 'Y', 'Y'),
        ('Y', 'X', 'Y'),
        ('Y', 'Y', 'X'),
    ]

    sampler = StatevectorSampler(seed=42)
    results = {}

    circuits = [create_ghz_and_measure(n_qubits, bases) for bases in mermin_bases]
    pubs = [(circ,) for circ in circuits]
    job = sampler.run(pubs, shots=shots)
    result = job.result()

    for i, bases in enumerate(mermin_bases):
        label = ''.join(bases)
        counts = result[i].data.meas.get_counts()
        corr = compute_correlator(counts, n_qubits)
        results[label] = round(corr, 6)
        print(f"    ⟨{label}⟩ = {corr:+.4f}")

    # M_3 = ⟨XXX⟩ - ⟨XYY⟩ - ⟨YXY⟩ - ⟨YYX⟩
    m3 = results['XXX'] - results['XYY'] - results['YXY'] - results['YYX']
    print(f"    M_3 (ideal) = {m3:.4f}  (teórico = 4.000)")
    return results, round(m3, 6)


def run_real_qpu(n_qubits, shots):
    """Envía el experimento al QPU real de IBM."""
    print(f"\n--- Ejecución REAL en QPU físico de IBM ---")

    # 1. Conectar a IBM
    token = get_ibm_token()
    print("[1/5] Conectando a IBM Quantum Platform...")

    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

    service = QiskitRuntimeService(
        channel="ibm_quantum_platform",
        token=token,
        instance="open-instance"
    )

    backend_name = "ibm_marrakesh"
    print(f"[2/5] Seleccionando QPU: {backend_name}...")
    backend = service.backend(backend_name)
    status = backend.status()
    print(f"       operational={status.operational}, pending_jobs={status.pending_jobs}")

    if not status.operational:
        # Intentar otro backend disponible
        print("       ibm_marrakesh no operacional, buscando alternativa...")
        for b in service.backends():
            s = b.status()
            if s.operational:
                backend = b
                backend_name = b.name
                print(f"       Usando: {backend_name} ({b.num_qubits}Q)")
                break

    # 2. Crear circuitos
    mermin_bases = [
        ('X', 'X', 'X'),
        ('X', 'Y', 'Y'),
        ('Y', 'X', 'Y'),
        ('Y', 'Y', 'X'),
    ]

    print(f"[3/5] Creando {len(mermin_bases)} circuitos GHZ({n_qubits}) + medición Mermin...")
    circuits = [create_ghz_and_measure(n_qubits, bases) for bases in mermin_bases]
    labels = [''.join(b) for b in mermin_bases]

    # 3. Transpilar para el hardware real
    print("[4/5] Transpilando para topología física del chip...")
    pm = generate_preset_pass_manager(optimization_level=3, backend=backend)
    transpiled = pm.run(circuits)

    for i, tc in enumerate(transpiled):
        ops = tc.count_ops()
        ecr_count = ops.get('ecr', 0) + ops.get('cx', 0)
        print(f"       Circuito '{labels[i]}': depth={tc.depth()}, 2Q_gates={ecr_count}")

    # 4. Enviar al QPU real
    print(f"[5/5] Enviando al QPU real ({shots} shots por circuito)...")
    sampler = SamplerV2(mode=backend)
    pubs = [(tc,) for tc in transpiled]
    job = sampler.run(pubs, shots=shots)
    job_id = job.job_id()
    print(f"       Job ID: {job_id}")
    print(f"       Esperando resultados del QPU físico...")

    result = job.result()
    print(f"       ¡Resultados recibidos!")

    # 5. Analizar resultados físicos
    correlators = {}
    details = {}
    for i, label in enumerate(labels):
        counts = result[i].data.meas.get_counts()
        corr = compute_correlator(counts, n_qubits)
        correlators[label] = round(corr, 6)

        # Top 4 bitstrings más frecuentes (datos crudos)
        top = dict(sorted(counts.items(), key=lambda x: -x[1])[:6])

        num_y = label.count('Y')
        sign = +1 if num_y == 0 else -1

        details[label] = {
            "correlator_measured": round(corr, 6),
            "mermin_sign": sign,
            "contribution": round(sign * corr, 6),
            "top_bitstrings": top,
            "total_counts": sum(counts.values())
        }

        print(f"    ⟨{label}⟩ = {corr:+.4f} (sign={sign:+d}, "
              f"contribution={sign * corr:+.4f})")

    # M_3 = ⟨XXX⟩ - ⟨XYY⟩ - ⟨YXY⟩ - ⟨YYX⟩
    m3 = sum(d["contribution"] for d in details.values())
    print(f"\n    ===== RESULTADO DESIGUALDAD DE MERMIN =====")
    print(f"    M_3 (QPU real) = {m3:.4f}")
    print(f"    Cota clásica:    2.0000")
    print(f"    Valor ideal GHZ: 4.0000")
    violation = m3 > 2.0
    print(f"    VIOLACIÓN:       {'SÍ ✓' if violation else 'NO ✗'}")
    if violation:
        print(f"    → Evidencia física de entrelazamiento cuántico genuino.")
    else:
        print(f"    → La decoherencia del chip impidió una violación clara.")

    return {
        "backend_name": backend_name,
        "backend_qubits": backend.num_qubits,
        "job_id": job_id,
        "correlators": correlators,
        "details": details,
        "mermin_value": round(m3, 6),
        "violation": violation
    }


def main():
    t0 = time.perf_counter()
    n_qubits = 3
    shots = 4000

    print("=" * 65)
    print("EXPERIMENTO REAL: DESIGUALDAD DE MERMIN EN IBM QUANTUM")
    print("=" * 65)
    print(f"Estado: GHZ de {n_qubits} qubits")
    print(f"Mediciones: {shots} shots por circuito")
    print(f"Desigualdad: M_3 = ⟨XXX⟩ - ⟨XYY⟩ - ⟨YXY⟩ - ⟨YYX⟩")
    print(f"Cota clásica: |M_3| ≤ 2")
    print(f"Valor cuántico ideal: |M_3| = 4")

    # Paso A: Simulación ideal (referencia)
    ideal_corr, ideal_m3 = run_ideal_simulation(n_qubits, shots)

    # Paso B: Ejecución en QPU real
    qpu_result = run_real_qpu(n_qubits, shots)

    t1 = time.perf_counter()

    # Compilar reporte final
    report = {
        "experiment_type": "REAL_QUANTUM_PHYSICS_MEASUREMENT",
        "title": "Mermin Inequality Violation on Physical QPU (GHZ State)",
        "reference": "Mermin, N.D. (1990) PRL 65, 1838",
        "what_this_proves": (
            "A violation of the Mermin inequality (M_3 > 2) constitutes "
            "physical evidence of genuine tripartite quantum entanglement "
            "that CANNOT be explained by any local hidden variable theory. "
            "This measurement can ONLY be performed on real quantum hardware."
        ),
        "ghz_qubits": n_qubits,
        "shots_per_circuit": shots,
        "ideal_simulation": {
            "correlators": ideal_corr,
            "mermin_value": ideal_m3,
            "note": "Simulación local sin ruido como referencia teórica"
        },
        "physical_qpu": {
            "backend": qpu_result["backend_name"],
            "total_qubits": qpu_result["backend_qubits"],
            "job_id": qpu_result["job_id"],
            "correlators": qpu_result["correlators"],
            "mermin_value": qpu_result["mermin_value"],
            "classical_bound": 2.0,
            "quantum_ideal": 4.0,
            "violation_detected": qpu_result["violation"],
            "raw_measurement_details": qpu_result["details"]
        },
        "comparison": {
            "ideal_mermin": ideal_m3,
            "physical_mermin": qpu_result["mermin_value"],
            "decoherence_loss": round(ideal_m3 - qpu_result["mermin_value"], 4),
            "fidelity_ratio": round(qpu_result["mermin_value"] / ideal_m3, 4)
                              if ideal_m3 != 0 else 0.0
        },
        "total_experiment_time_seconds": round(t1 - t0, 2)
    }

    # Persistir en PostgreSQL 16
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
              json.dumps(report), 'REAL_QPU_MERMIN_INEQUALITY_GHZ'))
        conn.commit()
        cur.close()
        conn.close()
        print("\n[DB] Persistido en PostgreSQL 16 (session_context).")
    except Exception as e:
        print(f"\n[DB WARN] Error al persistir: {e}")

    print("\n=== REPORTE FINAL ===")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    main()
