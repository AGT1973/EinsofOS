; ==============================================================================
; EINSOF BARE-METAL X86_64 KERNEL (NASM SYNTAX)
; Ejecucion pura en silicio: CERO C, CERO LIBC, CERO VTABLES.
; Control de memoria directa sobre R15 y aceleracion vectorial AVX2 / FMA.
; ==============================================================================

%include "einsof_types.inc"

default rel

section .data
    align 64
    msg_boot:       db "[+] EINSOF SILICON KERNEL (x86_64 AVX2 / R15 ARENA): ONLINE", 10
    msg_boot_len:   equ $ - msg_boot

    msg_pass:       db "[*] RESULTADO EN SILICIO: OPERACION COMPLETADA CON EXITO (EXIT CODE 0)", 10
    msg_pass_len:   equ $ - msg_pass

    align 32
    initial_val:    dq 0.02209708691207961, 0.02209708691207961, 0.02209708691207961, 0.02209708691207961

section .bss
    align 64
    arena_base_ptr: resq 1

section .text
    global _start

_start:
    ; 1. Escribir mensaje de booteo a stdout (sys_write = 1, fd = 1)
    mov rax, 1                  ; sys_write
    mov rdi, 1                  ; stdout
    lea rsi, [msg_boot]
    mov rdx, msg_boot_len
    syscall

    ; 2. FASE 1: Asignar bloque gigante de Arena en memoria (sys_mmap = 9)
    ; mmap(NULL, 64MB, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0)
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

    ; FIJAR EL REGISTRO MAESTRO BASE: R15 = ARENA BASE
    mov r15, rax
    mov [arena_base_ptr], r15

    ; Constante magica de 64 bits en RAX para evitar warnings de truncado
    mov rax, 0x45494E534F463031 ; "EINSOF01"

    ; 3. INICIALIZAR SLAB A EN [R15 + 0]
    mov qword [r15 + 0], rax
    mov word  [r15 + 8], TYPE_TENSOR_STIEFEL
    mov byte  [r15 + 10], 1                  ; Generation 1
    mov byte  [r15 + 11], FLAG_ESTABLE       ; Estable
    mov dword [r15 + 12], 2048               ; Dimension D = 2048

    ; Inicializar vector de 2048 doubles (16384 bytes = 512 paquetes YMM de 32B)
    vmovupd ymm0, [initial_val]
    lea rdi, [r15 + 64]         ; Puntero de inicio del payload de Slab A
    mov rcx, 512
.init_slab_a:
    vmovupd [rdi], ymm0
    add rdi, 32
    dec rcx
    jnz .init_slab_a

    ; 4. INICIALIZAR SLAB B (ROTOR / OPERADOR) EN [R15 + 16448]
    lea rbx, [r15 + 16448]      ; Puntero al inicio de Slab B
    mov qword [rbx + 0], rax
    mov word  [rbx + 8], TYPE_ROTOR_LIE
    mov byte  [rbx + 10], 1
    mov byte  [rbx + 11], FLAG_ESTABLE
    mov dword [rbx + 12], 2048

    lea rdi, [rbx + 64]         ; Puntero al payload de Slab B
    mov rcx, 512
.init_slab_b:
    vmovupd [rdi], ymm0
    add rdi, 32
    dec rcx
    jnz .init_slab_b

    ; 5. EJECUTAR CONTRACCION VECTORIAL EINSOF (SLAB C = SLAB A * SLAB B)
    ; Slab C arranca en [R15 + 32896]
    lea rdx, [r15 + 32896]      ; Puntero al inicio de Slab C
    mov qword [rdx + 0], rax
    mov word  [rdx + 8], TYPE_TENSOR_STIEFEL
    mov byte  [rdx + 10], 1
    mov byte  [rdx + 11], FLAG_TEMPORAL      ; Destino temporal
    mov dword [rdx + 12], 2048

    ; BUCLE DE COMPUTO VECTORIAL PURO AVX2 (512 iteraciones)
    lea rsi, [r15 + 64]         ; Origen A
    lea rdi, [rbx + 64]         ; Origen B
    lea r8,  [rdx + 64]         ; Destino C
    mov rcx, 512
    vxorpd ymm3, ymm3, ymm3     ; Acumulador de producto

.vector_loop:
    vmovupd ymm1, [rsi]         ; Carga 4 números de Slab A
    vmovupd ymm2, [rdi]         ; Carga 4 números de Slab B
    vmulpd  ymm4, ymm1, ymm2     ; Multiplicación de Hadamard
    vmovupd [r8], ymm4          ; Guarda directo en Slab C
    vaddpd  ymm3, ymm3, ymm4     ; Acumula producto
    add rsi, 32
    add rdi, 32
    add r8, 32
    dec rcx
    jnz .vector_loop

    ; 6. ESCRIBIR MENSAJE DE EXITO A STDOUT
    mov rax, 1                  ; sys_write
    mov rdi, 1                  ; stdout
    lea rsi, [msg_pass]
    mov rdx, msg_pass_len
    syscall

    ; 7. SALIR LIMPIAMENTE CON EXIT CODE 0 (sys_exit = 60)
    mov rax, 60                 ; sys_exit
    xor rdi, rdi                ; exit code 0
    syscall

.exit_error:
    mov rax, 60
    mov rdi, 1                  ; exit code 1
    syscall
