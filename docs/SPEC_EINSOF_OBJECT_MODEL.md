# ESPECIFICACIÓN DEL MODELO DE OBJETOS EINSOF (V1.0)
## Arquitectura de Fat Pointers (16 Bytes) y Slabs en Silicio Puro x86_64

---

### 1. Filosofía: Objetos sin C++, sin Vtables y sin Garbage Collector

En el Lenguaje Einsof, un **Objeto** no es una clase pesada de C++ ni un objeto empaquetado de Python.
Un Objeto se compone de exactamente dos partes físicas en memoria:
1. **El Descriptor de Manejo (`FatPtr` de 16 Bytes):** Vive en registros de CPU (`RDX:RAX`) o en la pila.
2. **El Bloque de Silicio (`Slab` alineado a 64 Bytes):** Vive en la memoria física a partir de `[R15 + offset]`.

---

### 2. Anatomía del `FatPtr` (16 Bytes / 128 Bits)

El `FatPtr` cabe en dos registros de 64 bits de la CPU x86_64 (`RAX` y `RDX`), permitiendo pasajes de parámetros de costo cero:

```
+-------------------------------------------------------------------------------+
|                        ESTRUCTURA BINARIA DEL FAT POINTER                     |
|                                (16 Bytes = 128 Bits)                          |
+-------------------+-------------------+---------------------------------------+
| Campo             | Tamaño / Registro | Descripción en Silicio                |
+-------------------+-------------------+---------------------------------------+
| payload_offset    | 64 bits (RAX)     | Desplazamiento desde la base R15      |
| meta_descriptor   | 64 bits (RDX)     | Metadatos compactados (ver desglose)  |
+-------------------+-------------------+---------------------------------------+
```

#### Desglose del `meta_descriptor` (64 bits en RDX):
```
Bits 00 - 15 (16 bits): TYPE_ID       -> Identificador del Tipo de Objeto (0x0001..0xFFFF).
Bits 16 - 23 (08 bits): GENERATION    -> Generación / Época del Slab (anti Use-After-Free).
Bits 24 - 31 (08 bits): FLAGS         -> Banderas de estado (Estable/Temporal, ReadOnly, PCIe).
Bits 32 - 63 (32 bits): DIMENSION_D   -> Dimensión D del tensor o tamaño del búfer.
```

#### Tabla de `TYPE_ID` Fundamentales:
- `0x0001` - **TENSOR_STIEFEL:** Tensor continuo ortonormal en $\mathcal{S}^{D-1}$.
- `0x0002` - **ROTOR_LIE:** Operador de rotación en $\mathrm{SO}(D)$ / Álgebra de Clifford.
- `0x0003` - **ATRACTOR_LYAPUNOV:** Estado atractor de bifurcación continua.
- `0x0004` - **FRAMEBUFFER_UI:** Búfer efímero de píxeles para proyección en pantalla.
- `0x0005` - **BUFFER_MMIO_PCIE:** Mapeo directo a tarjeta de red (NIC) o almacenamiento NVMe.

---

### 3. Cabecera del Slab (`SlabHeader` de 64 Bytes = 1 Línea de Caché)

Cada bloque asignado en memoria física está precedido o encabezado por 64 bytes alineados:

```
Offset (Hex)  Tamaño   Tipo de Dato   Campo               Descripción
0x00 - 0x07   8 Bytes  uint64_t       magic_cookie        0x45494E534F463031 ("EINSOF01")
0x08 - 0x09   2 Bytes  uint16_t       type_id             Tipo de entidad que aloja
0x0A - 0x0A   1 Byte   uint8_t        generation          Número de generación activo
0x0B - 0x0B   1 Byte   uint8_t        flags               Banderas (Bit 0: Estable, Bit 1: Temporal)
0x0C - 0x0F   4 Bytes  uint32_t       dim_d               Dimensión del tensor alojado
0x10 - 0x17   8 Bytes  uint64_t       alloc_bitmap        Bitmap de ocupación interna (alloc/free O(1))
0x18 - 0x1F   8 Bytes  uint64_t       neumaier_norm_sq    Última norma calculada (precisión 1e-15)
0x20 - 0x27   8 Bytes  uint64_t       crypto_hmac         Firma de integridad BLAKE2s
0x28 - 0x3F   24 Bytes uint8_t[24]    reserved_padding    Relleno para completar los 64 bytes
-------------------------------------------------------------------------------------------------------
Total: 64 Bytes exactos = 1 Línea de Caché de CPU
```

---

### 4. Dispatch de Métodos en Assembler (Cero Vtables)

En C++, llamar a un método implica buscar en la memoria el puntero de la vtable del objeto (`mov rax, [rcx]; call [rax + 16]`), provocando hasta 2 fallos de caché.

En Einsof, el dispatch de métodos se realiza mediante un **Jump Table global indexado por `TYPE_ID`**:

```nasm
; Llamada al método ROTAR para un objeto dado en RDX:RAX
; RDX contiene el meta_descriptor (los 16 bits bajos son el TYPE_ID)
movzx ebx, dx                           ; Extrae TYPE_ID de los 16 bits bajos de RDX
shl   rbx, 5                            ; Multiplica por 32 bytes (offset de tabla de métodos)
call  [tabla_metodos_global + rbx + 0]  ; Salta directamente a la rutina del tipo
```

**Ventaja en Silicio:**
1. Cero bytes extra por objeto (ahorro de 8 bytes de puntero vtable en cada instancia).
2. La tabla de métodos vive en memoria de solo lectura de CPU (`.rodata`), permanentemente caliente en la caché L1.
3. Máxima velocidad de predicción de saltos de la CPU.
