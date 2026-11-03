# ARQUITECTURA DE ASINCRONÍA TOTAL POR EVENTOS, HILO-NÚCLEO Y CRON
## El Motor Reactor Asíncrono de Silicio de EinsofOS

---

### 1. La Regla Sagrada: "Ningún Hilo se Bloquea Jamás"

En los sistemas operativos viejos (Windows / Linux tradicional), los programas se la pasan durmiendo (`sleep`, `wait`, bloqueo esperando lectura de disco). Cada vez que un hilo se bloquea, el kernel gasta miles de ciclos de reloj guardando registros y cambiando de contexto (`context switch`), vaciando la memoria caché L1/L2.

En **EinsofOS**, la arquitectura se basa en **Asincronía Total por Eventos (Reactor de Silicio)**:
1. **Cero Bloqueo:** Ninguna función espera a que el disco o la red respondan.
2. **Cero Hilos Ociosos:** El procesador solo se mueve cuando hay un evento real en el bus.
3. **Eventos en 64 Bytes:** Todo evento (un paquete de red, un byte del teclado, un timer del cron) es una estructura binaria exacta que cabe en **1 línea de caché de CPU**.

---

### 2. La Doctrina "Hilo por Núcleo Físico" (Thread-per-Core / Shared-Nothing)

Para exprimir al 100% los servidores multi-núcleo (como el Intel Core i3 de 4 núcleos de ALADIN o un AMD EPYC de 64 núcleos de datacenter):

EinsofOS asigna **exactamente 1 hilo dedicado por cada núcleo físico de CPU** fijado por afinidad de hardware:

```
+-----------------------------------------------------------------------------------+
|                        ASIGNACIÓN DEDICADA HILO-NÚCLEO EN ALADIN                  |
+-------------------+-------------------+-------------------+-----------------------+
| NÚCLEO 0 (CPU 0)  | NÚCLEO 1 (CPU 1)  | NÚCLEO 2 (CPU 2)  | NÚCLEO 3 (CPU 3)      |
+-------------------+-------------------+-------------------+-----------------------+
| RECEPTOR EVENTOS  | MOTOR TENSORIAL   | ALMACENAMIENTO    | RED Y COMUNICACIÓN    |
| Ring Buffer MMIO  | Álgebra Clifford  | DMA NVMe Directo  | Tráfico 100GbE / NIC  |
| Cron / Timers TSC | Variedad Stiefel  | Slabs Transac.    | Conexión Satelital    |
+-------------------+-------------------+-------------------+-----------------------+
```

**Ventaja Físico-Mecánica:**
- Los núcleos no compiten entre sí por la memoria caché.
- Cada núcleo procesa su propia cola de eventos lock-free en memoria RAM sin locks ni semáforos que frenen el reloj.

---

### 3. El Cron de Silicio (Temporizadores por Hardware TSC / APIC)

En lugar de programas `cron` pesados en espacio de usuario que despiertan cada minuto:

EinsofOS utiliza el **Time Stamp Counter (TSC)** del microprocesador x86_64 (`instrucción rdtsc`):
- Mide el paso del tiempo con **precisión de nanosegundos** (ciclos de reloj exactos del cristal de silicio).
- Permite programar eventos recurrentes:
  - *Micro-Cron (cada 10 ms):* Chequeo de señal satelital y deriva Stiefel.
  - *Meso-Cron (cada 5 minutos):* Sincronización de Slabs de memoria transaccional al NVMe.
  - *Macro-Cron (diario a las 4:00 AM):* Consolidación de balances COBOL y auditoría global.

---

### 4. Estructura Binaria de un Evento (64 Bytes = 1 Cache Line)

```
Offset (Hex)  Tamaño   Tipo de Dato   Campo               Descripción
0x00 - 0x07   8 Bytes  uint64_t       event_id            Identificador único incremental del evento
0x08 - 0x0F   8 Bytes  uint64_t       timestamp_tsc       Ciclo de CPU programado para disparo
0x10 - 0x11   2 Bytes  uint16_t       event_type          0x01=Red, 0x02=Disco, 0x03=Cron, 0x04=UI
0x12 - 0x13   2 Bytes  uint16_t       priority            Prioridad geodésica (0=Crítica, 255=Baja)
0x14 - 0x17   4 Bytes  uint32_t       target_core_id      Núcleo de CPU asignado para ejecución (0..N)
0x18 - 0x1F   8 Bytes  uint64_t       payload_slab_offset Puntero en la Arena R15 con los datos
0x20 - 0x27   8 Bytes  uint64_t       callback_fn_ptr     Dirección de memoria de la rutina en Assembler
0x28 - 0x3F   24 Bytes uint8_t[24]    custom_params       Parámetros inmediatos sin indirección
-------------------------------------------------------------------------------------------------------
Total: 64 Bytes exactos = 1 Línea de Caché L1
```
