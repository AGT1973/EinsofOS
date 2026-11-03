; ==============================================================================
; EINSOF NATIVE X86_64 TYPES & CONSTANTS (NASM SYNTAX)
; Arquitectura: Cero C, Cero Vtables, Fat Pointers de 16B y Slabs alineados a 64B
; ==============================================================================

; --- Identificadores de Tipos (TYPE_ID: 16 bits) ---
%define TYPE_TENSOR_STIEFEL     0x0001  ; Tensor continuo ortonormal en S^{D-1}
%define TYPE_ROTOR_LIE          0x0002  ; Operador de rotacion SO(D) / Clifford
%define TYPE_ATRACTOR_LYAPUNOV  0x0003  ; Atractor de minima accion / bifurcacion
%define TYPE_FRAMEBUFFER_UI     0x0004  ; Bufer efimero de proyeccion visual
%define TYPE_BUFFER_MMIO_PCIE   0x0005  ; Bufer directo de hardware (NIC / NVMe)

; --- Flags de Objeto (8 bits) ---
%define FLAG_ESTABLE            0x01    ; Persistente / Inmutable
%define FLAG_TEMPORAL           0x02    ; Efimero / Se destruye al usarse
%define FLAG_READONLY           0x04    ; Solo lectura
%define FLAG_PCIE_MAPPED        0x08    ; Mapeado directo por hardware MMIO

; --- Opcodes Geometricos Einsof (32 bits) ---
%define OP_ROT_LIE              0x00000001
%define OP_RETRACT_STIEFEL      0x00000002
%define OP_PROJECT_GRASSMANN    0x00000003
%define OP_CLIFFORD_MULT        0x00000004
%define OP_BIFURCATE_LYAPUNOV   0x00000005
%define OP_DMA_MMIO_IN          0x00000006
%define OP_DMA_MMIO_OUT         0x00000007
%define OP_HALT_STABLE          0x00000008

; --- Estructura FatPtr (16 Bytes exactos) ---
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
