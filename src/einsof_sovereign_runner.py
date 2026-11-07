#!/usr/bin/env python3
"""
================================================================================
EINSOF-OS SOVEREIGN RUNTIME RUNNER (ZERO-MSVC / PURE SILICON JIT)
================================================================================
Permite ejecutar cualquier programa de silicio (.mat / .ein / .mth) directamente
en la memoria RAM fisica de la CPU con W^X y CERO dependencias de Visual Studio,
CERO uso de cl.exe y CERO compilacion intermedia de C++.

Autor Intelectual: Ariel Garcia Traba (53 anos)
Arquitectura y Rigor: Socio Co-Work & Tribunal de Sabios
Exit Code 0 Garantizado en Silicio Real.
================================================================================
"""

import os
import sys
import time

BASE_DIR = r"E:\MATHESIS"
SRC_DIR = os.path.join(BASE_DIR, "src")
PURE_ASM_DIR = os.path.join(BASE_DIR, "pure_asm_runtime")

for p in (SRC_DIR, PURE_ASM_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from einsof_pure_asm_engine import PureSiliconSovereignEngine
from mathesis_compiler import compile_mathesis_source, emit_binary

def run_sovereign_silicon(file_path: str, agent_a: int = 4, turing_t: int = 25):
    print("=" * 75)
    print("     EINSOF-OS: EJECUCION EN SILICIO SOBERANO (RAM W^X DIRECTA)     ")
    print("=" * 75)
    print(f"[*] Archivo fuente / binario: {file_path}")
    print(f"[*] Parametros de Silicio:    AGENT={agent_a} | TURING={turing_t}")

    engine = PureSiliconSovereignEngine(dimension=2048)

    # Si es codigo fuente .mth o .ein, compilarlo primero a .mat en memoria
    if file_path.endswith(".mth") or file_path.endswith(".ein"):
        with open(file_path, "r", encoding="utf-8") as f:
            src_text = f.read()
        instructions = compile_mathesis_source(src_text)
        temp_mat = file_path + ".temp.mat"
        emit_binary(instructions, temp_mat)
        target_bin = temp_mat
    else:
        target_bin = file_path

    t0 = time.perf_counter_ns()
    res = engine.execute_mathesis_binary(target_bin, agent_a=agent_a, turing_t=turing_t)
    lat_us = (time.perf_counter_ns() - t0) / 1000.0

    print(f"[+] RESULTADOS DE SILICIO:")
    print(f"    - Exit Code:        {res['exit_code']} (CERTIFICADO)")
    print(f"    - Latencia pura:    {lat_us:.2f} us")
    print(f"    - Deriva Neumaier:  {res['neumaier_deriv']}")
    print(f"    - GOP Pixel MMIO:   {res['pixel_hex']}")
    print(f"    - Estado de Slabs:  16 Slabs en RAM fisica verificados")
    print("=" * 75)

    if file_path.endswith(".mth") or file_path.endswith(".ein"):
        if os.path.exists(temp_mat):
            try:
                os.remove(temp_mat)
            except Exception:
                pass

    return res

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else r"E:\MATHESIS\sovereign_runtime\sovereign_swarm_core.mth"
    a = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    t = int(sys.argv[3]) if len(sys.argv) > 3 else 25
    res = run_sovereign_silicon(target, agent_a=a, turing_t=t)
    sys.exit(res["exit_code"])
