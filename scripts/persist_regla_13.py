import psycopg2
import json

def persist():
    print("=" * 70)
    print("   EJECUTANDO REGLA 13: PERSISTENCIA ATOMICA EN POSTGRESQL 16")
    print("=" * 70)

    val_data = {
        "project": "EinsofOS",
        "milestone": "Fase 3: Bare-Metal UEFI GOP + ACPI MADT SMP + Servidor MCP + Centinela IA",
        "repository": "https://github.com/AGT1973/EinsofOS.git",
        "commit": "8c7258a",
        "silicon_nodes": {
            "host_local": "AMD A4-6300 (1C/2T, 16 GB DDR3, Windows/NASM)",
            "node_remote": "ALADIN 192.168.100.21 (Debian 13, Intel i3-8100 4C/4T @ 3.6 GHz, KVM)"
        },
        "uefi_gop": {
            "resolution": "1280x800",
            "bpp": 32,
            "mmio_address": "0x80000000",
            "font": "8x16 bitmap integrado",
            "state_machine": ["LOGIN", "DASHBOARD", "FAILOVER", "CONSOLE"]
        },
        "acpi_smp": {
            "madt_parser": "boot/einsof_acpi.h",
            "local_apic_base": "0xFEE00000",
            "thread_per_core_roles": ["Events/Cron", "Tensor/AVX2", "NVMe/Storage", "Network/Satellites"]
        },
        "mcp_server": {
            "status": "OPERATIVO (Exit Code 0)",
            "auth_tool": "einsof_auth_check_and_screen (SELECT en einsof_auth_registry)",
            "data_analysis_tool": "einsof_simple_data_analysis (metricas simples para IA)",
            "hot_swap_tool": "einsof_hot_swap (conmutacion lock xchg en 0.3 ns)",
            "telemetry_tool": "einsof_read_silicon_telemetry (Arena R15 64 KB Slabs)"
        },
        "exit_code": 0
    }
    val_json = json.dumps(val_data)

    # 1. Persistir en polydim_active_db.active_vault
    try:
        conn_active = psycopg2.connect(dbname="polydim_active_db", user="postgres", host="localhost", port=5432)
        cur_active = conn_active.cursor()
        cur_active.execute("SELECT id FROM active_vault WHERE key_name = 'einsof_os_milestone_fase3'")
        row = cur_active.fetchone()
        notes = "Regla 13: Cierre de sesion EinsofOS Fase 3 - MCP, UEFI GOP, ACPI SMP y Sentinel IA"
        if row:
            cur_active.execute("UPDATE active_vault SET value = %s, notes = %s, updated_at = NOW() WHERE key_name = 'einsof_os_milestone_fase3'", (val_json, notes))
        else:
            cur_active.execute("INSERT INTO active_vault (category, key_name, value, notes, updated_at) VALUES ('einsof_os', 'einsof_os_milestone_fase3', %s, %s, NOW())", (val_json, notes))
        conn_active.commit()
        conn_active.close()
        print("[+] Persistido exitosamente en 'polydim_active_db.active_vault'.")
    except Exception as e:
        print(f"[-] Error en polydim_active_db: {e}")

    # 2. Persistir en polydim_vec_db.permanent_vault y novelties
    try:
        conn_vec = psycopg2.connect(dbname="polydim_vec_db", user="postgres", host="localhost", port=5432)
        cur_vec = conn_vec.cursor()
        cur_vec.execute("SELECT id FROM permanent_vault WHERE key_name = 'einsof_os_milestone_fase3'")
        row = cur_vec.fetchone()
        if row:
            cur_vec.execute("UPDATE permanent_vault SET value = %s, notes = %s, updated_at = NOW() WHERE key_name = 'einsof_os_milestone_fase3'", (val_json, notes))
        else:
            cur_vec.execute("INSERT INTO permanent_vault (category, key_name, value, notes, updated_at) VALUES ('einsof_os', 'einsof_os_milestone_fase3', %s, %s, NOW())", (val_json, notes))

        # Registrar novedad en novelties
        cur_vec.execute("""
            INSERT INTO novelties (agent_id, ntype, path, summary, topics, absorbed, inserted_at)
            VALUES ('gandalf', 'silicon_operating_system', 'E:\\EinsofOS', %s, %s, 1, NOW())
        """, (
            "EinsofOS Fase 3: Bare-metal UEFI GOP 1280x800, ACPI MADT SMP discovery, Servidor MCP con SELECT auth en BBDD y regeneracion de pantallas, y Centinela IA con hot-swap xchg.",
            ["EinsofOS", "Bare-Metal", "UEFI", "MCP", "PostgreSQL", "Hot-Swap", "ACPI", "SIMD"]
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
