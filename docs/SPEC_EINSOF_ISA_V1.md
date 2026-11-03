# ESPECIFICACIÓN FORMAL DE LA ISA GEOMÉTRICA EINSOF (V1.0)
## Lenguaje de Ejecución Tensorial de Ultra-Bajo Nivel para Silicio e IA

---

### 1. La Unidad Atómica de Ejecución: `EinsofInstruction64`

Cada instrucción en el Lenguaje Einsof ocupa exactamente **64 bytes (512 bits)**, coincidiendo exactamente con una línea de caché L1/L2/L3 en la arquitectura moderna de servidores x86_64 y ARMv9.

#### Mapa de Memoria Binario (Little-Endian):
```
Offset (Hex)  Tamaño   Tipo de Dato   Identificador         Descripción
0x00 - 0x03   4 Bytes  uint32_t       opcode_id             Identificador del operador geométrico (0x01..0x08).
0x04 - 0x07   4 Bytes  uint32_t       dim_d                 Dimensión del espacio vectorial (D >= 1024).
0x08 - 0x0F   8 Bytes  uint64_t       slab_src_a            ID / Puntero físico al Slab de entrada A en RAM.
0x10 - 0x17   8 Bytes  uint64_t       slab_src_b            ID / Puntero físico al Slab de entrada B / Operador.
0x18 - 0x1F   8 Bytes  uint64_t       slab_dest             ID / Puntero físico al Slab de destino.
0x20 - 0x27   8 Bytes  double         epsilon_tol           Cota de tolerancia de error ortonormal (ej. 1e-15).
0x28 - 0x2F   8 Bytes  double         lyapunov_potential    Potencial energético / temperatura de bifurcación.
0x30 - 0x37   8 Bytes  uint64_t       crypto_sign           Firma de integridad BLAKE2s truncada a 64 bits.
0x38 - 0x3F   8 Bytes  uint64_t       next_trace            Offset o puntero a la siguiente instrucción de la trayectoria.
-----------------------------------------------------------------------------------------------------------------------
Total: 64 Bytes (512 bits) = 1 Línea de Caché de CPU
```

---

### 2. Tabla de Opcodes Geométricos (Cero Palabras Clave)

| Código Hex | Nemónico Simbólico | Nombre Matemático | Acción en Silicio |
| :--- | :--- | :--- | :--- |
| **`0x01`** | `ROT_LIE` | Rotación de Lie en $\mathrm{SO}(D)$ | Aplica $Y = X \cdot R$ donde $R \in \mathrm{SO}(D)$ preservando la distancia geodésica. |
| **`0x02`** | `RETRACT_STIEFEL` | Retracción Polar de Orden 4 | Proyecta la matriz a la variedad ortonormal $X(X^T X)^{-1/2}$ usando acumulación Neumaier ($\mathrm{error} \le 10^{-15}$). |
| **`0x03`** | `PROJECT_GRASSMANN` | Proyección Ortogonal | Proyecta $X$ sobre el subespacio de $B$: $P_B(X) = B B^T X$. Extrae subespacios invariantes. |
| **`0x04`** | `CLIFFORD_MULT` | Producto Geométrico de Clifford | Realiza la contracción y producto exterior en el álgebra $\mathcal{C}\ell(p, q)$. |
| **`0x05`** | `BIFURCATE_LYAPUNOV`| Control de Flujo por Atractor | Evalúa el potencial $\Phi(X)$; bifurca la ejecución hacia la cuenca de atracción de menor energía sin saltos `jmp` de texto. |
| **`0x06`** | `DMA_MMIO_IN` | Ingesta Directa por DMA | Mapea paquetes de red o bloques NVMe directo al Slab sin pasar por el kernel. |
| **`0x07`** | `DMA_MMIO_OUT` | Emisión Directa por DMA | Envía el contenido del Slab a la tarjeta de red o almacenamiento físico. |
| **`0x08`** | `HALT_STABLE` | Punto Fijo / Fin de Traza | Detiene el ciclo si el gradiente de energía $\| \nabla \Phi \| \le \epsilon$. |

---

### 3. Modelo de Memoria: El Slab de Silicio (`PmtpSlab`)

1. **Alineación Física:** Cada Slab en memoria física está alineado a límites de 64 bytes (o HugePages de 2 MB).
2. **Descriptor de Slab:**
   - `slab_id` (64 bits): Identificador único.
   - `dim_d` (32 bits): Dimensión del tensor.
   - `rank_k` (32 bits): Rango del subespacio ortonormal.
   - `payload`: Bloque contiguo de números en punto flotante IEEE-754 (float32 o float64).
3. **Cero Punteros Nulos / Cero Desbordamiento de Búfer:**
   - La ISA valida las cotas dimensionales a nivel de hardware antes de despachar las instrucciones a las unidades vectoriales SIMD.

---

### 4. Flujo de Control Continuo (Dinámica no Booleana)

Los sistemas operativos y lenguajes tradicionales deciden mediante comparaciones booleanas escalares:
```c
if (paquete_red == CORRECTO) {
    procesar();
} else {
    descartar();
}
```

En EinsofOS, las decisiones se toman por **atracción geométrica en una variedad continua**:
Dado un vector de estado $X$ y dos atractores $A_{\text{proc}}$ y $A_{\text{desc}}$:
$$\Delta E = \langle X, A_{\text{proc}} \rangle - \langle X, A_{\text{desc}} \rangle$$
Si $\Delta E > \text{lyapunov\_potential}$, la trayectoria geométrica fluye automáticamente hacia la instrucción apuntada por el atractor 1. No hay saltos condicionales frágiles ni ramas sujetas a fallos de predicción de bifurcación (`branch mispredictions`).
