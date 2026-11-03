#!/usr/bin/env python3
"""
test_silicon_pure_asm.py — Suite de Verificacion en Silicio Real (ALADIN Debian 13)
Valida la cadena completa: Einsof -> Assembler Puro (NASM) -> Silicio (Intel i3-8100 AVX2)
Sin C, sin libc, sin intermediarios.
"""

import subprocess
import os
import sys
import psycopg2

def run_test():
    print("=" * 70)
    print("  EINSOF SILICON CERTIFICATION SUITE: PURE X86_64 ASM (ZERO-C)  ")
    print("=" * 70)

    # 1. Generar codigo Assembler
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(base_dir, "src")
    gen_asm = os.path.join(src_dir, "generated_kernel.asm")
    types_inc = os.path.join(src_dir, "einsof_types.inc")

    sys.path.insert(0, src_dir)
    from einsof_asm_engine import EinsofAsmEmitter

    print("[1] Generando codigo fuente en Assembler Puro...")
    emitter = EinsofAsmEmitter(gen_asm)
    emitter.emit_header()
    emitter.emit_vector_hadamard(offset_a=0, offset_b=16448, offset_dest=32896, dim_d=2048)
    emitter.emit_footer()
    emitter.save()

    # 2. Sincronizar a nodo ALADIN
    print("[2] Sincronizando archivos a ALADIN (192.168.100.21)...")
    scp_cmd = f"scp {gen_asm} {types_inc} root@192.168.100.21:/root/einsof_baremetal/"
    res_scp = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)
    if res_scp.returncode != 0:
        print("[-] Error en SCP:", res_scp.stderr)
        return False

    # 3. Ensamblar con NASM y Enlazar con LD en ALADIN
    print("[3] Ensamblando con NASM y enlazando con LD (Cero compilador C)...")
    remote_build = (
        "cd /root/einsof_baremetal && "
        "nasm -f elf64 generated_kernel.asm -o generated_kernel.o && "
        "ld -s generated_kernel.o -o generated_kernel && "
        "./generated_kernel"
    )
    ssh_cmd = f'ssh root@192.168.100.21 "{remote_build}"'
    res_exec = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
    
    print("\n--- SALIDA CRUDA DE SILICIO EN ALADIN ---")
    print(res_exec.stdout.strip())
    if res_exec.stderr.strip():
        print("STDERR:", res_exec.stderr.strip())
    print(f"EXIT CODE: {res_exec.returncode}")
    print("-----------------------------------------\n")

    if res_exec.returncode == 0:
        print("[+] CERTIFICACION EXITOSA: El ejecutable de 8 KB corrio con EXIT CODE 0.")
        
        # 4. Persistir en PostgreSQL 16
        try:
            conn = psycopg2.connect("dbname=polydim_active_db user=postgres password=Imagina2022# host=localhost port=5432")
            cur = conn.cursor()
            cur.execute("SELECT id FROM active_vault WHERE key_name = 'EINSOF_PURE_ASM_SILICON_TEST';")
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE active_vault SET value = %s, updated_at = NOW() WHERE key_name = 'EINSOF_PURE_ASM_SILICON_TEST';", (res_exec.stdout.strip(),))
            else:
                cur.execute("INSERT INTO active_vault (category, key_name, value, notes, updated_at) VALUES ('silicon_test', 'EINSOF_PURE_ASM_SILICON_TEST', %s, 'Certificacion Exit Code 0 en ALADIN Intel i3-8100', NOW());", (res_exec.stdout.strip(),))
            conn.commit()
            conn.close()
            print("[+] Resultado persistido en PostgreSQL 16 (polydim_active_db.active_vault).")
        except Exception as e:
            print("[-] Error registrando en Postgres:", e)

        return True
    else:
        print("[-] Fallo en ejecucion de silicio.")
        return False

if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
