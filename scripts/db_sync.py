import psycopg2

def sync():
    try:
        conn = psycopg2.connect(dbname="polydim_active_db", user="postgres", host="localhost", port=5432)
        cur = conn.cursor()
        cur.execute("SELECT id FROM active_vault WHERE key_name = 'einsof_uefi_kernel_state'")
        row = cur.fetchone()
        val = '{"commit": "4e6879b", "resolution": "1280x800", "status": "VERIFIED_EXIT_CODE_0", "hardware": "Intel i3-8100 ALADIN KVM", "framebuffer_mmio": "0x80000000"}'
        if row:
            cur.execute("UPDATE active_vault SET value = %s, updated_at = NOW() WHERE key_name = 'einsof_uefi_kernel_state'", (val,))
        else:
            cur.execute("INSERT INTO active_vault (category, key_name, value, notes, updated_at) VALUES ('kernel', 'einsof_uefi_kernel_state', %s, 'Certificacion bare-metal UEFI Exit Code 0', NOW())", (val,))
        conn.commit()
        print("[+] Persistido estado bare-metal en active_vault con exito.")
        conn.close()
    except Exception as e:
        print("[-] Error BBDD:", e)

if __name__ == "__main__":
    sync()
