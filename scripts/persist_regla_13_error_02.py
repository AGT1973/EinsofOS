"""
Regla 13 - Persistencia atomica ERROR_02 (A/B test de latencia Antigravity/Gemini)
Solo hechos verificados con evidencia; hipotesis marcadas como tales. No se borra ni se oculta nada previo.
NO se persisten claves API (el mcp_config del plugin las tenia en texto plano: rotar).
"""
import json, datetime, os
import psycopg2

# La contrasena NO va en el codigo: definir PGPASSWORD en el entorno antes de ejecutar.
PGPASSWORD = os.environ["PGPASSWORD"]

REGISTRO = {
    "error_id": "ERROR_02_AB_LATENCIA_GEMINI_20261104",
    "fecha": "2026-11-04T19:43-03:00",
    "sintoma": "Clase del 4/11: Gemini se colgaba ('Working'), 15-20 min para levantar Flask, error 'servers experiencing high traffic'.",
    "correccion_a_ERROR_01": (
        "El diagnostico de las 15:13 (zombies + socket a ALADIN dentro del MCP) se presento como causa confirmada "
        "y NO estaba verificado. Queda como HIPOTESIS no probada."
    ),
    "verificado": {
        "hardware": "AMD A4-6300, 1 core / 2 hilos, carga CPU 100% al medir; RAM libre 5579 MB de 16340 MB",
        "zoom": "zTscoder.exe (conversor de grabacion Zoom) ~128% de un hilo, 692 s CPU acumulados post-reinicio",
        "mcp_antes": "Plugin build-with-google-polydim-compute lanzaba 11 servidores MCP; polydim duplicado (2 procesos, uno 666 MB). Rust mcp_*.exe inactivos (0 s CPU, 5 MB c/u)",
        "mcp_despues": "1 solo polydim_mcp_server.py (30 MB, 0.5 s CPU) tras desactivar mcp_config.json del plugin y reiniciar",
        "arranque_mcp": "initialize + tools/list = 2886 ms",
        "flask_bridge_v4": "import flask+requests+tools del bridge v4 = 1.24 s total, con Zoom activo -> Flask NO es el cuello",
        "a92f925c": (
            "Modelo en transcript: Claude Sonnet 5.5 (no Gemini). Herramientas locales 34 s (19:31:54-19:32:28). "
            "Puerto 5005 respondio success:true. Ultimo step=8 (resultado herramienta); falta respuesta final. "
            "polydim nuevo arranco 19:32:41, ~13 s despues del ultimo step: el reinicio de Antigravity pudo cortar la corrida (no probado). "
            "Consulta enviada a esa conversacion: sin respuesta."
        ),
        "esperas_modelo_transcripts": {
            "dd37667c": "gap 2504 s (~42 min) entre step 41 (resultado herramienta) y 43 (respuesta modelo); modelos: Claude Sonnet 4.6 Thinking y Gemini 3.8 Flash",
            "82a8fa64": "gap 1727 s (~29 min) entre step 75 y 77; varios modelos (Gemini 3.8 Flash, Claude Opus 4.6, GPT-OSS 120B)",
            "tool_local_lento": "138-170 s en pasos de ejecucion local de dd37667c (compatible con CPU saturada)"
        },
    },
    "hipotesis_no_probadas": [
        "Competencia por 1 nucleo (Zoom+Chrome+Antigravity+language_server) explica demoras locales",
        "Esperas de decenas de minutos son del lado del modelo/backend (coincide con error high traffic)",
        "El tamano de esta conversacion (800+ steps) agrega latencia propia",
        "Que el cambio del plugin mejore los tiempos: SIN evidencia aun",
    ],
    "cambios_aplicados": [
        "Renombrado plugins/build-with-google-polydim-compute/mcp_config.json -> mcp_config.json.DISABLED_AB_TEST (reversible)",
        "Backup: E:/POLYDIM_EINSOF/EINSOF_OS/backups/error_02_ab_test_20261104/",
        "Previo: eliminada handle_hacedor_vector_bounce del polydim_mcp_server.py y 3 hacedor_vector_bounce.json (15:10-15:13)",
    ],
    "seguridad": "mcp_config del plugin tenia claves API (Cerebras, Claude) en texto plano y aparecieron en el log de la conversacion: ROTAR. No se almacenan aqui.",
    "pendiente": [
        "Prueba limpia: conversacion nueva, Gemini, Zoom/zTscoder cerrados, misma orden, registrar hora inicio/fin",
        "Repetir en conversacion larga para aislar efecto del contexto",
        "Cruzar modelo activo en dd37667c steps 41-43",
    ],
}

detail = json.dumps(REGISTRO, ensure_ascii=False)
NOTA = "ERROR_02: A/B latencia Antigravity/Gemini. Hechos verificados vs hipotesis separados. Corrige sobreafirmacion de ERROR_01."

for db, table in (("polydim_active_db", "active_vault"), ("polydim_vec_db", "permanent_vault")):
    try:
        conn = psycopg2.connect(dbname=db, user="postgres", password=PGPASSWORD, host="localhost", port=5432)
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO {table} (category, key_name, value, notes, updated_at) VALUES (%s,%s,%s,%s,NOW())",
            ("ERROR_LOG", "ERROR_02_AB_LATENCIA_GEMINI_20261104", detail, NOTA),
        )
        cur.execute(
            f"SELECT COUNT(*), MAX(LENGTH(value)) FROM {table} WHERE key_name=%s",
            ("ERROR_02_AB_LATENCIA_GEMINI_20261104",),
        )
        n, ln = cur.fetchone()
        conn.commit()
        print(f"[OK] {db}.{table}: filas con key ERROR_02 = {n}, bytes value = {ln}")
        cur.close(); conn.close()
    except Exception as e:
        print(f"[FALLO] {db}.{table}: {type(e).__name__}: {e}")
