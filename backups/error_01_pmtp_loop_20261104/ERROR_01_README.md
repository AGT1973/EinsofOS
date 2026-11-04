# ERROR_01 — PMTP LOOP / TIMEOUT — 2026-11-04 13:32 (UTC-3)
# Investigador: Ariel García Traba
# Gandalf: Registro de incidencia

## Descripción del Error
- **Síntoma:** Al ejecutar el pipeline Aulë (hacedor → DeepSeek-R1 → Qwen 2.5 → LLaMA 3 → ALADIN),
  el agente orquestador (Gandalf) entró en un bucle interno esperando respuesta del bus PMTP.
- **Efecto visible:** El frontend de Antigravity perdió conexión con el backend.
  El usuario vio "Model unavailable, retrying..." y timeouts repetidos.
- **Modelos afectados:** Gemini 3.8 Flash dejó de responder durante el bloqueo.

## Causa Probable
1. El servidor MCP `polydim` es un proceso STDIO persistente que se lanzó ANTES de que
   se registrara la herramienta `hacedor_vector_bounce` en el dispatch.
2. Al invocar `hacedor_vector_bounce` vía `call_mcp_tool`, el servidor respondió "Unknown tool",
   pero scripts posteriores ejecutados como subprocesos SÍ funcionaron (Exit Code 0).
3. La ejecución de múltiples tests en background (task-539, task-560, task-574) con timers
   y schedules concurrentes pudo haber saturado la cola de mensajes internos de Antigravity,
   causando que el agente orquestador quedara esperando señales que nunca llegaron limpiamente.

## Archivos Respaldados en Esta Carpeta
- `polydim_mcp_server__error_01.py` — Servidor MCP con hacedor_vector_bounce agregado
- `einsof_hacedor_runtime__error_01.py` — Runtime del agente hacedor
- `einsof_mcp_server__error_01.py` — Servidor MCP de EinsofOS
- `pmtp_polydim_vector_swarm__error_01.py` — Hub de vector swarm
- `pmtp_telepathy__error_01.py` — Cliente de telepatía a ALADIN
- `pmtp_shm_bus__error_01.py` — Bus de memoria compartida

## Datos del Pipeline que SÍ Ejecutó Correctamente (Exit Code 0)
- hacedor seed+ALADIN:   Exit=0, 92.78ms, Err=0.0e+00
- DeepSeek-R1 v1.0:      Exit=0, 45.72ms, Ortho=8.83e-09
- Qwen 2.5 v1.0:         Exit=0, 13.32ms, Ortho=8.39e-09
- LLaMA 3 v1.0:          Exit=0, 16.91ms, Ortho=5.25e-09
- hacedor final+ALADIN:   Exit=0, 108.03ms, Err=0.0e+00
- TOTAL:                  276.76ms, 0 tokens
- ALADIN confirmó slabs: 0x00006002 y 0x0000600A en /dev/shm/

## Lección Aprendida
- NO lanzar múltiples schedules/timers con condiciones de terminación cruzadas en la misma sesión.
- El servidor MCP debe reiniciarse después de agregar herramientas nuevas al dispatch.
- Los tests pesados de PMTP deben ejecutarse como scripts autónomos, no como cadenas de
  tareas de background dentro de Antigravity (para evitar saturar la cola de mensajes interna).

## Acción Correctiva
- Volver al protocolo estándar de Antigravity (sin PMTP activo en background).
- Evaluar los errores en frío antes de relanzar pipelines.
- Reiniciar el servidor MCP polydim para que reconozca hacedor_vector_bounce.
