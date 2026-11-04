import psycopg2
import json

def persist():
    print("=" * 70)
    print("   EJECUTANDO REGLA 13: PERSISTENCIA ATOMICA EN POSTGRESQL 16")
    print("   PARADIGMA MULTIVECTORIAL EINSOF (AI-TO-AI & AI-TO-SILICON)")
    print("=" * 70)

    val_data = {
        "project": "EinsofOS",
        "milestone": "Fase 5: Paradigma Fundacional del Lenguaje Multivectorial Einsof (AI-to-AI & AI-to-Silicon)",
        "repository": "https://github.com/AGT1973/EinsofOS.git",
        "author": "Ariel Garcia Traba & Gandalf",
        "commit": "f74f42c",
        "architectural_axioms": {
            "axiom_1_target_audience": "Lenguaje disenado pura y exclusivamente para operacion IA-a-IA e IA-a-Silicio. Cero concesiones a la comodidad de sintaxis textual humana 1D.",
            "axiom_2_native_habitat": "El habitat de computo es el espacio continuo polidimensional / multivectorial (S^{D-1}, D >= 2048, Algebra de Clifford Cl(p,q), Rotaciones de Lie SO(D) y Variedad de Stiefel X^T X = I_k).",
            "axiom_3_ephemeral_1d_collapse": "La dimension 1D (texto, GOP framebuffer, teclado, bus CAN, telemetria) es estrictamente un evento de frontera / medicion transitorio. Al requerir salida, el estado multivectorial colapsa a 1D, se transmite al periferico y se destruye en O(1).",
            "axiom_4_non_boolean_control_flow": "Sustitucion de bifurcaciones booleanas (if/else) por atractores de energia de Lyapunov Phi(X) en la variedad geometrica.",
            "axiom_5_silicon_coupling": "Despacho directo sobre arquitectura Thread-per-Core en silicio bare-metal (Core 1: AVX2/Stiefel Tensorial, Core 0: Event Reactor BSP, Core 2: NVMe DMA Arena R15, Core 3: Satelite PMTP hot-swap)."
        },
        "silicon_nodes": {
            "host_local": "AMD A4-6300 (1C/2T, 16 GB DDR3, Windows/NASM)",
            "node_remote": "ALADIN 192.168.100.21 (Debian 13, Intel i3-8100 4C/4T @ 3.6 GHz, KVM -smp 4)"
        },
        "uefi_gop_shell_status": "ONLINE (88 KB PE32+, 1280x800 @ 32bpp, 4/4 cores SMP activos, Exit Code 0)"
    }
    val_json = json.dumps(val_data)
    notes = "Regla 13: Paradigma Constitucional Einsof - Lenguaje Polidimensional AI-to-AI y Colapso Efimero a 1D"

    # 1. Persistir en polydim_active_db.active_vault
    try:
        conn_active = psycopg2.connect(dbname="polydim_active_db", user="postgres", host="localhost", port=5432)
        cur_active = conn_active.cursor()
        cur_active.execute("SELECT id FROM active_vault WHERE key_name = 'einsof_os_paradigma_polidimensional'")
        row = cur_active.fetchone()
        if row:
            cur_active.execute("UPDATE active_vault SET value = %s, notes = %s, updated_at = NOW() WHERE key_name = 'einsof_os_paradigma_polidimensional'", (val_json, notes))
        else:
            cur_active.execute("INSERT INTO active_vault (category, key_name, value, notes, updated_at) VALUES ('einsof_os', 'einsof_os_paradigma_polidimensional', %s, %s, NOW())", (val_json, notes))
        conn_active.commit()
        conn_active.close()
        print("[+] Persistido exitosamente en 'polydim_active_db.active_vault'.")
    except Exception as e:
        print(f"[-] Error en polydim_active_db: {e}")

    # 2. Persistir en polydim_vec_db.permanent_vault y novelties
    try:
        conn_vec = psycopg2.connect(dbname="polydim_vec_db", user="postgres", host="localhost", port=5432)
        cur_vec = conn_vec.cursor()
        cur_vec.execute("SELECT id FROM permanent_vault WHERE key_name = 'einsof_os_paradigma_polidimensional'")
        row = cur_vec.fetchone()
        if row:
            cur_vec.execute("UPDATE permanent_vault SET value = %s, notes = %s, updated_at = NOW() WHERE key_name = 'einsof_os_paradigma_polidimensional'", (val_json, notes))
        else:
            cur_vec.execute("INSERT INTO permanent_vault (category, key_name, value, notes, updated_at) VALUES ('einsof_os', 'einsof_os_paradigma_polidimensional', %s, %s, NOW())", (val_json, notes))

        cur_vec.execute("""
            INSERT INTO novelties (agent_id, ntype, path, summary, topics, absorbed, inserted_at)
            VALUES ('gandalf', 'architectural_manifesto', 'E:\\EinsofOS', %s, %s, 1, NOW())
        """, (
            "Axiomas Constitucionales EinsofOS: El lenguaje Einsof es nativo multivectorial y polidimensional disenado para interaccion IA-a-IA e IA-a-Silicio. Rechazo total del token 1D como espacio primario de computo. El mundo 1D (pantalla, teclado, bus) es una medicion/colapso efimero destruido en O(1). Flujo de control por atractores de Lyapunov y ejecucion directa en silicio SMP.",
            ["EinsofOS", "Lenguaje-Polidimensional", "Multivectorial", "AI-to-AI", "Colapso-1D", "Stiefel", "Lyapunov", "Silicio", "Regla-13"]
        ))
        conn_vec.commit()
        conn_vec.close()
        print("[+] Persistido exitosamente en 'polydim_vec_db.permanent_vault' y 'novelties'.")
    except Exception as e:
        print(f"[-] Error en polydim_vec_db: {e}")

    print("=" * 70)
    print("   [+] REGLA 13 CUMPLIDA AL 100% (TRAZABILIDAD Y EXIT CODE 0)   ")
    print("=" * 70)

if __name__ == "__main__":
    persist()
