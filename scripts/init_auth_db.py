import psycopg2
import hashlib

def init_auth():
    print("[*] Conectando a PostgreSQL 16 (polydim_active_db)...")
    conn = psycopg2.connect(dbname="polydim_active_db", user="postgres", host="localhost", port=5432)
    cur = conn.cursor()

    print("[*] Creando tabla 'einsof_auth_registry'...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS einsof_auth_registry (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(64) UNIQUE NOT NULL,
            token_hash VARCHAR(128) NOT NULL,
            clearance_level INT NOT NULL DEFAULT 1,
            role_description VARCHAR(64) NOT NULL,
            is_authorized BOOLEAN NOT NULL DEFAULT TRUE,
            allowed_screens JSONB NOT NULL DEFAULT '["login", "dashboard", "failover", "telemetry"]'::jsonb,
            last_login_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    users = [
        ("ariel_einsof", "ariel_soberano_2026", 10, "Investigador Soberano y Creador", True),
        ("admin", "admin_einsof", 5, "Administrador de Silicio", True),
        ("sigma_prime", "tensor_ai_key", 8, "Agente IA Autonomo", True),
        ("guest_unauthorized", "wrong_key", 0, "Intruso No Autorizado", False)
    ]

    for u_id, secret, clearance, role, auth in users:
        thash = hashlib.sha256(secret.encode()).hexdigest()
        cur.execute("""
            INSERT INTO einsof_auth_registry (user_id, token_hash, clearance_level, role_description, is_authorized, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                token_hash = EXCLUDED.token_hash,
                clearance_level = EXCLUDED.clearance_level,
                role_description = EXCLUDED.role_description,
                is_authorized = EXCLUDED.is_authorized;
        """, (u_id, thash, clearance, role, auth))

    conn.commit()
    print("[+] Tabla 'einsof_auth_registry' inicializada con 4 identidades soberanas.")

    cur.execute("SELECT user_id, role_description, is_authorized FROM einsof_auth_registry ORDER BY clearance_level DESC;")
    for row in cur.fetchall():
        print(f"    - {row[0]}: {row[1]} | Autorizado: {row[2]}")

    conn.close()

if __name__ == "__main__":
    init_auth()
