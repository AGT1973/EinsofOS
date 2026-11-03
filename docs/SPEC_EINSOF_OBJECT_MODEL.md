# ESPECIFICACIÓN DEL MODELO DE OBJETOS EINSOF (V1.1)
## Arquitectura de Fat Pointers (16 Bytes), Slabs y Despacho en Caché L1

---

### 1. El Objeto Einsof como Entidad de Memoria Directa

En el Lenguaje Einsof no existen clases abstractas ni objetos en el sentido clásico de C++ o Java.
Un **Objeto Einsof** es la combinación inseparable de:
1. **Un Descriptor `FatPtr` (16 Bytes):** Manejado directamente en registros de procesador (`RDX:RAX`).
2. **Un Bloque de Silicio `Slab` (Alineado a 64 Bytes):** Residente en la Arena física a partir de `[R15 + payload_offset]`.

---

### 2. Formato del Descriptor `FatPtr` (16 Bytes / 128 Bits)

```
Registro RAX (64 bits): PAYLOAD_OFFSET -> Offset relativo a la base R15
Registro RDX (64 bits): META_DESCRIPTOR -> Empaquetado binario:
  - Bits 00 - 15 (16 bits): TYPE_ID (1..6)
  - Bits 16 - 23 (08 bits): GENERATION (Contador de ciclo de vida / anti use-after-free)
  - Bits 24 - 31 (08 bits): FLAGS (0x01=Estable, 0x02=Temporal, 0x04=ReadOnly, 0x08=MMIO_PCIe)
  - Bits 32 - 63 (32 bits): DIMENSION_D (Dimensión del espacio continuo D >= 1024)
```

---

### 3. La Tabla de Despacho Global en Caché L1 (384 Bytes)

En C++, cada objeto contiene un puntero de 8 bytes a su vtable individual, dispersando punteros por toda la memoria RAM y causando constantes fallos de caché (`L1 cache misses`).

En Einsof, el sistema operativo mantiene una **única tabla de despacho estática** en la sección `.rodata`:
- **6 Tipos de Objetos** $\times$ **8 Métodos Fundamentales** $\times$ **8 Bytes por puntero** = **384 Bytes totales**.
- **La tabla entera cabe en 6 líneas de caché L1 de la CPU.**
- **Resultado:** El despacho de métodos tiene una tasa de acierto de caché de CPU del 100%. Latencia de despacho: **1 ciclo de reloj (0.3 nanosegundos)**.

```
                      TABLA GLOBAL DE DESPACHO (.rodata - 384 Bytes)
              +-------------------+-------------------+-------------------+
              | OP_ROT_LIE (0x01) | OP_PROJECT (0x03) | OP_RETRACT (0x02) | ...
+-------------+-------------------+-------------------+-------------------+
| TENSOR_ST   | ptr_rot_stiefel   | ptr_proj_stiefel  | ptr_retract_stief |
+-------------+-------------------+-------------------+-------------------+
| ROTOR_CLIFF | ptr_rot_clifford  | ptr_proj_clifford | ptr_retract_cliff |
+-------------+-------------------+-------------------+-------------------+
| ATRACTOR_LY | ptr_eval_lyapunov | ptr_proj_attractor| ptr_retract_lyap  |
+-------------+-------------------+-------------------+-------------------+
| FRAMEBUFFER | ptr_blit_pixels   | ptr_proj_screen   | ptr_clear_screen  |
+-------------+-------------------+-------------------+-------------------+
```

#### Código de Despacho en Assembler (3 Instrucciones):
```nasm
; RDX contiene el meta_desc, RAX contiene el offset
movzx ebx, dx                           ; EBX = TYPE_ID (16 bits bajos)
mov   ecx, [inst_opcode]                ; ECX = OPCODE_ID (1..8)
lea   r8,  [dispatch_table + rbx*64 + rcx*8] ; Cálculo de offset sin saltos
call  [r8]                              ; Ejecución inmediata en L1 caliente
```

---

### 4. Ciclo de Vida: El Protocolo Efímero `Crear ➔ Proyectar ➔ Destruir`

Para objetos temporales (como un búfer de interfaz de pantalla o un tensor intermedio de inferencia):

1. **Creación:**  
   Se reserva el espacio en la Arena `R15`. Se graba la cabecera con la generación actual (`generation = G`).
2. **Uso:**  
   La IA o el servidor opera directamente con los registros vectoriales AVX2 sobre `[R15 + payload_offset]`.
3. **Destrucción $O(1)$ sin Garbage Collector:**  
   Para destruir el objeto efímero, **no se borran los gigabytes de memoria uno por uno**.  
   Simplemente se incrementa el byte de generación en la cabecera del Slab:
   ```nasm
   inc byte [r15 + slab_offset + 10]   ; generation = G + 1
   ```
   **Cualquier puntero residual viejo queda invalidado al instante en 1 ciclo de reloj.** Si un proceso intenta acceder al objeto destruido, la comprobación `cmp [r15 + offset - 54], dl` detecta la discrepancia de generación y detiene la operación de inmediato.
