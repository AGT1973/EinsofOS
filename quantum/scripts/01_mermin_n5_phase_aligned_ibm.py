# -*- coding: utf-8 -*-
"""
DESAFÍO 1: VIOLACIÓN CORREGIDA DE MERMIN N=5 CON ALINEACIÓN DE FASE EN QPU FÍSICO
=================================================================================
Problema cuántico SOTA: En el experimento previo en QPU (Job dbmbbf674qds73ds02jg),
el estado GHZ canonical sin fase (|00000> + |11111>)/sqrt(2) arrojó M_5 = -0.4790 (~0).
Demostración analítica de Einsof:
  Para N=5, <psi(phi)| M_5 |psi(phi)> = 16 * sin(phi).
  - Con phi = 0 (GHZ estándar sin fase): sin(0) = 0 -> M_5 = 0.0 (anulación teórica).
  - Con phi = pi/2 (Einsof Phase Alignment via compuerta S en q0): sin(pi/2) = 1.0 -> M_5 = +16.0!
    Cota clásica: |M_5| <= 4.0. Máximo cuántico: 16.0 (Superación del 400%).

Este script:
1. Compara mecánicamente el estado estándar sin fase (M_5 = 0) vs Einsof con fase S (M_5 = 16.0).
2. Transpila y envía los 16 circuitos con compuerta S al hardware superconductor de IBM.
3. Transfiere la matriz de los 16 correladores directamente a PMTP ShmBus (SLAB_ID = 0x504D0015)
   aplicando retracción polar de Stiefel S^{15} con acumulador compensado de Neumaier.
4. Persiste atómicamente el reporte y Job ID en PostgreSQL 16 con Exit Code 0.

Autor: Ariel García Traba (Independent Research / EinsofOS)
Directiva: Honestidad radical, contrato de silicio, Exit Code 0.
"""

import sys
import os
import time
import json
import math
import numpy as np
from itertools import combinations

# Inclusión de librerías PMTP
sys.path.insert(0, "E:/PMTP")
from pmtp_polydim_vector_swarm import PersistentMmapSlabBus

# Inclusión de Qiskit e IBM Runtime
from qiskit import QuantumCircuit
from qiskit.primitives import StatevectorSampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
import psycopg2


def neumaier_norm(vec: np.ndarray) -> float:
    s = 0.0
    c = 0.0
    for x in vec:
        val = float(x) * float(x)
        t = s + val
        if abs(s) >= abs(val):
            c += (s - t) + val
        else:
            c += (val - t) + s
        s = t
    return float(math.sqrt(max(0.0, s + c)))


def get_ibm_token():
    conn = psycopg2.connect("dbname=polydim_active_db user=postgres password=postgres host=localhost port=5432")
    cur = conn.cursor()
    cur.execute("SELECT value FROM active_vault WHERE key_name = 'ibm_quantum_api_key'")
    token = cur.fetchone()[0]
    conn.close()
    return token


def generate_mermin_5q_bases():
    bases_with_signs = []
    positions = list(range(5))
    # n_Y = 1: C(5,1) = 5 bases, sign = +1
    for y_pos in combinations(positions, 1):
        b = ['X'] * 5
        b[y_pos[0]] = 'Y'
        bases_with_signs.append((tuple(b), +1))
    # n_Y = 3: C(5,3) = 10 bases, sign = -1
    for y_pos in combinations(positions, 3):
        b = ['X'] * 5
        for p in y_pos:
            b[p] = 'Y'
        bases_with_signs.append((tuple(b), -1))
    # n_Y = 5: C(5,5) = 1 base, sign = +1
    bases_with_signs.append((('Y', 'Y', 'Y', 'Y', 'Y'), +1))
    return bases_with_signs


def build_circuit(bases, apply_phase_s=True):
    qc = QuantumCircuit(5)
    # Paso 1: Preparar GHZ
    qc.h(0)
    if apply_phase_s:
        # Alineación de fase óptima de Einsof: rotación S (pi/2) sobre el qubit raíz
        # Transforma (|00000> + |11111>)/sqrt(2) -> (|00000> + i|11111>)/sqrt(2)
        qc.s(0)
    for i in range(1, 5):
        qc.cx(0, i)
    qc.barrier()
    # Paso 2: Rotar a la base de medición
    for q, b in enumerate(bases):
        if b == 'X':
            qc.h(q)
        elif b == 'Y':
            qc.sdg(q)
            qc.h(q)
    qc.measure_all()
    return qc


def compute_correlator(counts):
    total = sum(counts.values())
    if total == 0:
        return 0.0
    val = 0.0
    for bits, count in counts.items():
        parity = bits.replace(' ', '').count('1') % 2
        val += count * ((-1) ** parity)
    return val / total


def main():
    t0 = time.perf_counter()
    shots = 4000
    backend_choice = sys.argv[1] if len(sys.argv) > 1 else "ibm_fez"
    
    print("=" * 80)
    print("DESAFÍO CUÁNTICO SOTA 1: VIOLACIÓN CORREGIDA DE MERMIN N=5 EN QPU FÍSICO")
    print("TEOREMA EINSOF: ALINEACIÓN DE FASE S (pi/2) vs GHZ CANÓNICO (0 CORRELACIÓN)")
    print("=" * 80)
    
    bases_signs = generate_mermin_5q_bases()
    print(f"Total de correladores de Mermin evaluados: {len(bases_signs)}")
    
    # 1. Verificación en simulación ideal Statevector
    print("\n[FASE 1: VERIFICACIÓN TEÓRICA / ANALÍTICA EN SIMULADOR]")
    sampler = StatevectorSampler(seed=42)
    
    # Corrida A: GHZ Canónico sin fase
    circs_std = [build_circuit(b, apply_phase_s=False) for b, s in bases_signs]
    res_std = sampler.run([(c,) for c in circs_std], shots=shots).result()
    m5_std = sum(sign * compute_correlator(res_std[i].data.meas.get_counts()) 
                 for i, (_, sign) in enumerate(bases_signs))
    
    # Corrida B: Einsof GHZ con fase S
    circs_einsof = [build_circuit(b, apply_phase_s=True) for b, s in bases_signs]
    res_einsof = sampler.run([(c,) for c in circs_einsof], shots=shots).result()
    m5_einsof_ideal = sum(sign * compute_correlator(res_einsof[i].data.meas.get_counts()) 
                          for i, (_, sign) in enumerate(bases_signs))
    
    print(f"  GHZ Estándar (phi=0):    M_5 = {m5_std:+.4f} (Teórico = 0.0000 - Cero Correlación)")
    print(f"  Einsof GHZ (phi=pi/2):   M_5 = {m5_einsof_ideal:+.4f} (Teórico = +16.0000 - Máximo Cuántico)")
    print(f"  Cota clásica (LHV):      |M_5| <= 4.0000")
    print(f"  Superación teórica:      {m5_einsof_ideal / 4.0:.2f}x sobre el límite de variable oculta local")
    
    # 2. Ejecución Física en IBM Quantum QPU
    print(f"\n[FASE 2: EJECUCIÓN EN HARDWARE CUÁNTICO FÍSICO ({backend_choice})]")
    token = get_ibm_token()
    service = QiskitRuntimeService(channel="ibm_quantum_platform", token=token, instance="open-instance")
    backend = service.backend(backend_choice)
    status = backend.status()
    print(f"  QPU seleccionado: {backend.name} ({backend.num_qubits} qubits, operational={status.operational})")
    print(f"  Trabajos pendientes en cola: {status.pending_jobs}")
    
    # Transpilar para ISA del chip
    pm = generate_preset_pass_manager(optimization_level=3, backend=backend)
    transpiled_circs = pm.run(circs_einsof)
    
    print(f"  Circuitos transpilados para topología nativa de {backend.name}.")
    print(f"  Enviando 16 circuitos al criostato ({shots} shots cada uno = 64,000 mediciones)...")
    
    sampler_qpu = SamplerV2(mode=backend)
    pubs = [(tc,) for tc in transpiled_circs]
    job = sampler_qpu.run(pubs, shots=shots)
    job_id = job.job_id()
    job_url = f"https://quantum.ibm.com/jobs/{job_id}"
    print(f"  Job ID encolado: {job_id}")
    print(f"  URL IBM Quantum: {job_url}")
    print(f"  Esperando procesamiento físico...")
    
    qpu_result = job.result()
    latencia_s = time.perf_counter() - t0
    print(f"  ¡Resultados físicos recibidos en {latencia_s:.2f} s!")
    
    # Analizar resultados físicos
    correlators_physical = []
    m5_qpu = 0.0
    for i, (b, sign) in enumerate(bases_signs):
        label = ''.join(b)
        counts = qpu_result[i].data.meas.get_counts()
        corr = compute_correlator(counts)
        contrib = sign * corr
        m5_qpu += contrib
        correlators_physical.append(corr)
        
    violation = abs(m5_qpu) > 4.0
    
    print("\n" + "=" * 80)
    print("RESULTADO FÍSICO MERMIN N=5 CON ALINEACIÓN DE FASE EINSOF")
    print("=" * 80)
    print(f"  M_5 (QPU Físico {backend.name}): {m5_qpu:+.4f}")
    print(f"  Cota Clásica (LHV):             4.0000")
    print(f"  Valor Teórico Ideal:           16.0000")
    print(f"  Violación Irrefutable:          {'SÍ ✓' if violation else 'NO (Atenuado por decoherencia)'}")
    print(f"  Ratio Físico / Cota Clásica:    {abs(m5_qpu)/4.0:.3f}")
    
    # 3. Ingesta atómica a PMTP Shared Memory Slab (SLAB_ID = 0x504D0015)
    # 16 correladores continuos en la hipersfera S^{15}
    v_corr = np.array(correlators_physical, dtype=np.float64)
    v_norm = neumaier_norm(v_corr)
    v_stiefel = v_corr / v_norm
    drift_stiefel = abs(neumaier_norm(v_stiefel) - 1.0)
    
    bus = PersistentMmapSlabBus()
    slab_id = 0x504D0015
    meta_slab = bus.write_tensor_slab(slab_id, v_stiefel)
    
    read_back, _ = bus.read_tensor_slab(slab_id)
    shm_diff = float(np.max(np.abs(v_stiefel - read_back)))
    
    # 4. Compilar y persistir en PostgreSQL 16
    report_data = {
        "desafio": "SOTA Quantum Mermin-Ardehali-Belinskii-Klyshko N=5 Phase Aligned Violation",
        "teorema_demostrado": "<psi(phi)| M_5 |psi(phi)> = 16 * sin(phi)",
        "simulacion_ideal": {
            "ghz_estandar_sin_fase": m5_std,
            "einsof_fase_pi_2": m5_einsof_ideal,
            "cota_clasica": 4.0
        },
        "qpu_fisico": {
            "backend": backend.name,
            "job_id": job_id,
            "job_url": job_url,
            "total_shots": shots * len(bases_signs),
            "m5_qpu_medido": round(m5_qpu, 4),
            "violacion_detectada": violation,
            "ratio_sobre_cota_clasica": round(abs(m5_qpu)/4.0, 3)
        },
        "pmtp_bus": {
            "slab_id": meta_slab["slab_id_hex"],
            "dim": meta_slab["dim"],
            "stiefel_drift": drift_stiefel,
            "shm_diff": shm_diff,
            "tokens_en_chat": 0
        },
        "exit_code": 0
    }
    
    conn = psycopg2.connect("dbname=polydim_vec_db user=postgres password=postgres host=localhost port=5432")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO session_context (conversation_id, summary, category, created_at)
        VALUES (%s, %s, %s, NOW())
        RETURNING id;
    """, ('c8f6b7cd-c96d-4bc0-9428-ccccee03234c', json.dumps(report_data), 'DESAFIO_SOTA_1_MERMIN_5Q_PHASE_ALIGNMENT_SUPERIORITY'))
    row_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("MATRIZ DE SUPERIORIDAD EMPÍRICA DESAFÍO 1 (PERSISTIDA EN DB_ID:", row_id, ")")
    print("=" * 80)
    print(f"  Job ID Oficial:    {job_id}")
    print(f"  URL IBM:           {job_url}")
    print(f"  M_5 Sin Fase:      {m5_std:+.4f} (Fallo del paradigma estándar)")
    print(f"  M_5 Einsof Fase:   {m5_einsof_ideal:+.4f} ideal / {m5_qpu:+.4f} en QPU real")
    print(f"  Slab PMTP:         {meta_slab['slab_id_hex']} ({meta_slab['dim']*8} bytes)")
    print(f"  Tokens en Chat:    0 TOKENS")
    print(f"  Exit Code:         0")
    print("=" * 80)
    
    return report_data


if __name__ == "__main__":
    main()
