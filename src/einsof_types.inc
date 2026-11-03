; ==============================================================================
; EINSOF NATIVE X86_64 TYPES & CONSTANTS (NASM SYNTAX) - V1.1 EXPANDIDA
; Arquitectura: Cero C, Cero Vtables, Fat Pointers de 16B y Slabs alineados a 64B
; ==============================================================================

; --- Identificadores de Tipos de Objetos (TYPE_ID: 16 bits) ---
%define TYPE_TENSOR_STIEFEL         0x0001  ; Tensor continuo ortonormal en S^{D-1}
%define TYPE_SUBSPACE_GRASSMANN     0x0002  ; Subespacio matricial k x D
%define TYPE_ROTOR_CLIFFORD         0x0003  ; Rotor par Spin(D) / Algebra de Clifford
%define TYPE_ATRACTOR_DYNAMICS      0x0004  ; Atractor de minima accion / bifurcacion continua
%define TYPE_FRAMEBUFFER_EPHEMERAL  0x0005  ; Bufer efimero de proyeccion visual (Crear -> Mostrar -> Destruir)
%define TYPE_STREAM_DMA_PCIE        0x0006  ; Canal directo de hardware (NIC 100GbE / NVMe)

; --- Flags de Objeto (8 bits) ---
%define FLAG_ESTABLE                0x01    ; Persistente / Inmutable (ROM/Slab Fijo)
%define FLAG_TEMPORAL               0x02    ; Efimero / Se destruye al usarse en RAM
%define FLAG_READONLY               0x04    ; Solo lectura
%define FLAG_PCIE_MAPPED            0x08    ; Mapeado directo por hardware MMIO
%define FLAG_DIRTY                  0x10    ; Modificado pendiente de sync

; --- Opcodes Geometricos / Metodos Einsof (32 bits) ---
%define OP_ROT_LIE                  0x00000001  ; Rotacion de fase en SO(D)
%define OP_RETRACT_STIEFEL          0x00000002  ; Retraccion polar a S^{D-1} (Neumaier <= 1e-15)
%define OP_PROJECT_GRASSMANN        0x00000003  ; Proyeccion ortogonal de subespacio
%define OP_CLIFFORD_MULT            0x00000004  ; Contraccion / Producto geometrico
%define OP_BIFURCATE_LYAPUNOV       0x00000005  ; Flujo por gradiente de energia de atractor
%define OP_TRANSFER_DMA             0x00000006  ; Transferencia rafaga PCIe Zero-Copy
%define OP_DESTROY_EPHEMERAL        0x00000007  ; Destruccion O(1) e invalidacion de generacion
%define OP_HALT_STABLE              0x00000008  ; Punto fijo / Fin de traza

; --- Estructura FatPtr (16 Bytes exactos - Cabe en RDX:RAX) ---
struc FatPtr
    .payload_offset: resq 1     ; Offset relativo al registro base R15 (8 bytes)
    .meta_desc:      resq 1     ; [dim:32 | flags:8 | gen:8 | type_id:16] (8 bytes)
endstruc

; --- Estructura SlabHeader (64 Bytes exactos = 1 Cache Line) ---
struc SlabHeader
    .magic:          resq 1     ; 0x45494E534F463031 ("EINSOF01")
    .type_id:        resw 1     ; 2 bytes
    .generation:     resb 1     ; 1 byte
    .flags:          resb 1     ; 1 byte
    .dim_d:          resd 1     ; 4 bytes
    .alloc_bitmap:   resq 1     ; 8 bytes
    .neumaier_norm:  resq 1     ; 8 bytes (double IEEE-754)
    .crypto_hmac:    resq 1     ; 8 bytes
    .reserved:       resb 24    ; 24 bytes de padding para completar 64 bytes
endstruc

; --- Macro de Ensamblado: Empaquetar Meta en RDX ---
; %1: type_id (16b), %2: gen (8b), %3: flags (8b), %4: dim (32b)
%macro PACK_FAT_META 4
    mov rdx, %4
    shl rdx, 8
    or  rdx, %3
    shl rdx, 8
    or  rdx, %2
    shl rdx, 16
    or  rdx, %1
%endmacro
