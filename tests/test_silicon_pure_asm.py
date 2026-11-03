#!/usr/bin/env python3
"""
test_silicon_pure_asm.py — Suite de Verificacion en Silicio Real (ALADIN Debian 13)
Valida la ejecucion de 4 operadores vectoriales puros AVX2:
ROT_LIE, PROJECT_GRASSMANN, RETRACT_STIEFEL, DESTROY_EPHEMERAL.
Sin C, sin libc, sin vtables, sin intermediarios.
"""

import subprocess
import os
import sys
import psycopg2

def run_test():
    print("=" * 75)
    print("  EINSOF SILICON CERTIFICATION SUITE: PURE X86_64 ASM V1.1 (ZERO-C)  ")
    print("=" * 75)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(base_dir, "src")
    kernel_asm = os.path.join(src_dir, "einsof_kernel.asm")
    types_inc = os.path.join(src_dir, "einsof_types.inc")

    # 1. Sincronizar archivos a ALADIN
    print("[1] Sincronizando kernel nativo y tipos a ALADIN (192.168.100.21)...")
    scp_cmd = f"scp {kernel_asm} {types_inc} root@192.168.100.21:/root/einsof_baremetal/"
    res_scp = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)
    if res_scp.returncode != 0:
        print("[-] Error en SCP:", res_scp.stderr)
        return False

    # 2. Ensamblar con NASM y Enlazar con LD en ALADIN
    print("[2] Ensamblando con NASM 2.16 y enlazando con LD (Cero compilador C)...")
    remote_build = (
        "cd /root/einsof_baremetal && "
        "nasm -f elf64 einsof_kernel.asm -o einsof_kernel.o && "
        "ld -s einsof_kernel.o -o einsof_kernel && "
        "./einsof_kernel"
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
        print("[+] CERTIFICACION TOTAL EXITOSA: 4 Operadores Geometricos ejecutados con EXIT CODE 0.")
        
        # 3. Persistir en PostgreSQL 16
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
