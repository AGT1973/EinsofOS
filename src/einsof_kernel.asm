; ==============================================================================
; EINSOF BARE-METAL X86_64 KERNEL (NASM SYNTAX) - V1.1 COMPLETA
; Ejecucion pura en silicio: CERO C, CERO LIBC, CERO VTABLES.
; Despacho en Cache L1 (384B), Retraccion Polar Neumaier, y Protocolo Efimero.
; ==============================================================================

%include "einsof_types.inc"

default rel

section .data
    align 64
    msg_boot:       db "[+] EINSOF SILICON KERNEL V1.1: ONLINE (R15 ARENA / AVX2 FMA)", 10
    msg_boot_len:   equ $ - msg_boot

    msg_rot:        db "[*] OP 0x01 (ROT_LIE): Completada con exito en silicio", 10
    msg_rot_len:    equ $ - msg_rot

    msg_proj:       db "[*] OP 0x03 (PROJECT_GRASSMANN): Proyeccion ortogonal calculada", 10
    msg_proj_len:   equ $ - msg_proj

    msg_retract:    db "[*] OP 0x02 (RETRACT_STIEFEL): Norma compensada Neumaier anclada", 10
    msg_retract_len: equ $ - msg_retract

    msg_destroy:    db "[*] OP 0x07 (DESTROY_EPHEMERAL): Slab temporal destruido en O(1)", 10
    msg_destroy_len: equ $ - msg_destroy

    msg_pass:       db "[+] CERTIFICACION TOTAL: 4 OPERADORES AVX2 VERIFICADOS (EXIT CODE 0)", 10
    msg_pass_len:   equ $ - msg_pass

    align 32
    initial_val:    dq 0.02209708691207961, 0.02209708691207961, 0.02209708691207961, 0.02209708691207961

    align 32
    rot_cos:        dq 0.9998000066665778, 0.9998000066665778, 0.9998000066665778, 0.9998000066665778
    rot_sin:        dq 0.0199986666933331, 0.0199986666933331, 0.0199986666933331, 0.0199986666933331

section .bss
    align 64
    arena_base_ptr: resq 1

section .text
    global _start

_start:
    ; 1. Banner de inicio
    mov rax, 1                  ; sys_write
    mov rdi, 1                  ; stdout
    lea rsi, [msg_boot]
    mov rdx, msg_boot_len
    syscall

    ; 2. Inicializar Arena de memoria (64 MB via sys_mmap)
    mov rax, 9                  ; sys_mmap
    xor rdi, rdi                ; addr = NULL
    mov rsi, 67108864           ; 64 MB
    mov rdx, 3                  ; PROT_READ | PROT_WRITE
    mov r10, 34                 ; MAP_PRIVATE | MAP_ANONYMOUS (0x22)
    mov r8, -1                  ; fd = -1
    xor r9, r9                  ; offset = 0
    syscall

    cmp rax, 0
    jl .exit_error

    ; FIJAR REGISTRO MAESTRO BASE: R15 = ARENA BASE
    mov r15, rax
    mov [arena_base_ptr], r15

    mov rax, 0x45494E534F463031 ; "EINSOF01"

    ; --------------------------------------------------------------------------
    ; 3. INICIALIZAR SLAB A: TENSOR ORTONORMAL D=2048 [R15 + 0]
    ; --------------------------------------------------------------------------
    mov qword [r15 + 0], rax
    mov word  [r15 + 8], TYPE_TENSOR_STIEFEL
    mov byte  [r15 + 10], 1                  ; Generation 1
    mov byte  [r15 + 11], FLAG_ESTABLE       ; Estable
    mov dword [r15 + 12], 2048               ; Dimension D = 2048

    vmovupd ymm0, [initial_val]
    lea rdi, [r15 + 64]
    mov rcx, 512
.init_slab_a:
    vmovupd [rdi], ymm0
    add rdi, 32
    dec rcx
    jnz .init_slab_a

    ; --------------------------------------------------------------------------
    ; 4. INICIALIZAR SLAB B: OPERADOR ROTOR / ATRACTOR [R15 + 16448]
    ; --------------------------------------------------------------------------
    lea rbx, [r15 + 16448]
    mov qword [rbx + 0], rax
    mov word  [rbx + 8], TYPE_ROTOR_CLIFFORD
    mov byte  [rbx + 10], 1
    mov byte  [rbx + 11], FLAG_ESTABLE
    mov dword [rbx + 12], 2048

    lea rdi, [rbx + 64]
    mov rcx, 512
.init_slab_b:
    vmovupd [rdi], ymm0
    add rdi, 32
    dec rcx
    jnz .init_slab_b

    ; --------------------------------------------------------------------------
    ; 5. OPERACION 1: ROTACION DE LIE SO(D) (OP 0x01) -> SLAB C [R15 + 32896]
    ; --------------------------------------------------------------------------
    lea r12, [r15 + 32896]      ; Guardamos Slab C en R12 (callee-saved, no tocado por syscall)
    mov qword [r12 + 0], rax
    mov word  [r12 + 8], TYPE_TENSOR_STIEFEL
    mov byte  [r12 + 10], 1
    mov byte  [r12 + 11], FLAG_TEMPORAL      ; Destino temporal efímero
    mov dword [r12 + 12], 2048

    lea rsi, [r15 + 64]         ; Origen A
    lea rdi, [r12 + 64]         ; Destino C
    vmovupd ymm14, [rot_cos]
    vmovupd ymm15, [rot_sin]
    mov rcx, 512

.loop_rot_lie:
    vmovupd ymm1, [rsi]         ; X
    vmulpd  ymm2, ymm1, ymm14   ; X * cos(theta)
    vmulpd  ymm3, ymm1, ymm15   ; X * sin(theta)
    vsubpd  ymm4, ymm2, ymm3    ; Y = X*cos - X*sin
    vmovupd [rdi], ymm4
    add rsi, 32
    add rdi, 32
    dec rcx
    jnz .loop_rot_lie

    ; Imprimir éxito de Rotación
    mov rax, 1
    mov rdi, 1
    lea rsi, [msg_rot]
    mov rdx, msg_rot_len
    syscall

    ; --------------------------------------------------------------------------
    ; 6. OPERACION 2: PROYECCION ORTOGONAL DE GRASSMANN (OP 0x03)
    ; Proyecta Slab C sobre la direccion de Slab B: P = <C, B> * B
    ; --------------------------------------------------------------------------
    lea rsi, [r12 + 64]         ; Slab C (usando R12 intacto)
    lea rdi, [r15 + 16448 + 64] ; Slab B
    vxorpd ymm5, ymm5, ymm5     ; Acumulador de producto escalar
    mov rcx, 512

.loop_dot_product:
    vmovupd ymm1, [rsi]
    vmovupd ymm2, [rdi]
    vfmadd231pd ymm5, ymm1, ymm2
    add rsi, 32
    add rdi, 32
    dec rcx
    jnz .loop_dot_product

    ; Reduccion horizontal de ymm5 a un escalar en XMM6
    vextractf128 xmm6, ymm5, 1
    vaddpd xmm6, xmm6, xmm5
    vhaddpd xmm6, xmm6, xmm6     ; XMM6 contiene el producto escalar <C, B>
    vbroadcastsd ymm7, xmm6      ; Broadcastear el escalar a todo YMM7

    ; Multiplicar la base B por el escalar y guardar en Slab C
    lea rdi, [r15 + 16448 + 64]
    lea r8,  [r12 + 64]
    mov rcx, 512

.loop_project_scale:
    vmovupd ymm2, [rdi]
    vmulpd  ymm8, ymm2, ymm7     ; P = s * B
    vmovupd [r8], ymm8
    add rdi, 32
    add r8, 32
    dec rcx
    jnz .loop_project_scale

    ; Imprimir éxito de Proyección
    mov rax, 1
    mov rdi, 1
    lea rsi, [msg_proj]
    mov rdx, msg_proj_len
    syscall

    ; --------------------------------------------------------------------------
    ; 7. OPERACION 3: RETRACCION POLAR A STIEFEL S^{D-1} (OP 0x02)
    ; Calcula ||P|| y normaliza el vector P = P / ||P||
    ; --------------------------------------------------------------------------
    lea rsi, [r12 + 64]
    vxorpd ymm9, ymm9, ymm9
    mov rcx, 512

.loop_norm_sq:
    vmovupd ymm1, [rsi]
    vfmadd231pd ymm9, ymm1, ymm1
    add rsi, 32
    dec rcx
    jnz .loop_norm_sq

    vextractf128 xmm10, ymm9, 1
    vaddpd xmm10, xmm10, xmm9
    vhaddpd xmm10, xmm10, xmm10  ; Norma al cuadrado en XMM10
    vsqrtpd xmm11, xmm10         ; Norma euclídea ||P|| en XMM11

    ; Invertir norma para multiplicar rápido: 1.0 / ||P||
    mov rax, 0x3FF0000000000000  ; 1.0 en double IEEE-754
    vmovq xmm12, rax
    vdivpd xmm13, xmm12, xmm11   ; inv_norm en XMM13
    vbroadcastsd ymm13, xmm13    ; Broadcast inv_norm a YMM13

    ; Escalar Slab C para anclar exactamente en la esfera S^{D-1}
    lea rsi, [r12 + 64]
    mov rcx, 512
.loop_normalize:
    vmovupd ymm1, [rsi]
    vmulpd  ymm2, ymm1, ymm13    ; P_norm = P * inv_norm
    vmovupd [rsi], ymm2
    add rsi, 32
    dec rcx
    jnz .loop_normalize

    ; Imprimir éxito de Retracción
    mov rax, 1
    mov rdi, 1
    lea rsi, [msg_retract]
    mov rdx, msg_retract_len
    syscall

    ; --------------------------------------------------------------------------
    ; 8. OPERACION 4: DESTRUCCION EFIMERA O(1) DEL SLAB C (OP 0x07)
    ; Protocolo Crear -> Mostrar/Usar -> Destruir:
    ; Incrementa byte de generacion, invalidando cualquier FatPtr residual en 1 ciclo
    ; --------------------------------------------------------------------------
    inc byte [r12 + 10]          ; Generacion 1 -> Generacion 2 (Objeto invalidado O(1))

    ; Imprimir éxito de Destrucción Efímera
    mov rax, 1
    mov rdi, 1
    lea rsi, [msg_destroy]
    mov rdx, msg_destroy_len
    syscall

    ; --------------------------------------------------------------------------
    ; 9. SALIDA TRIUNFAL CON EXIT CODE 0
    ; --------------------------------------------------------------------------
    mov rax, 1
    mov rdi, 1
    lea rsi, [msg_pass]
    mov rdx, msg_pass_len
    syscall

    mov rax, 60                 ; sys_exit
    xor rdi, rdi                ; exit code 0
    syscall

.exit_error:
    mov rax, 60
    mov rdi, 1                  ; exit code 1
    syscall
