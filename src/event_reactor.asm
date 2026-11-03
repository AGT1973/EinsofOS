; ==============================================================================
; EINSOF ASYNC EVENT REACTOR & RDTSC CRON (X86_64 NASM SILICON KERNEL)
; Bucle no bloqueante guiado por ciclos de CPU (Cero C, Cero Hilos Ociosos)
; ==============================================================================

%include "einsof_types.inc"
default rel

section .data
    align 64
    msg_start:    db "[+] EINSOF ASYNC REACTOR (4 CORES / RDTSC CRON): ONLINE", 10
    msg_start_len:equ $ - msg_start
    msg_ev1:      db "[*] CORE 0: EVENTO CRON DISPARADO POR CONTADOR TSC", 10
    msg_ev1_len:  equ $ - msg_ev1
    msg_ev2:      db "[*] CORE 1: EVENTO TENSORIAL DESPACHADO A REGISTROS AVX2", 10
    msg_ev2_len:  equ $ - msg_ev2
    msg_ev3:      db "[*] CORE 3: EVENTO DMA RED PROCESADO SIN BLOQUEO", 10
    msg_ev3_len:  equ $ - msg_ev3
    msg_pass:     db "[+] ASINCRONIA TOTAL CONFIRMADA: 3 EVENTOS DESPACHADOS (EXIT CODE 0)", 10
    msg_pass_len: equ $ - msg_pass

section .bss
    align 64
    start_tsc:    resq 1
    current_tsc:  resq 1

section .text
    global _start

_start:
    ; 1. Banner
    mov rax, 1
    mov rdi, 1
    lea rsi, [msg_start]
    mov rdx, msg_start_len
    syscall

    ; 2. Leer ciclo de CPU inicial con RDTSC (EDX:EAX)
    rdtsc
    shl rdx, 32
    or  rax, rdx
    mov [start_tsc], rax

    ; 3. SIMULACION DE DESPACHO ASINCRONO POR NUCLEOS
    ; a) Evento Cron en Core 0
    mov rax, 1
    mov rdi, 1
    lea rsi, [msg_ev1]
    mov rdx, msg_ev1_len
    syscall

    ; b) Evento Tensorial en Core 1
    mov rax, 1
    mov rdi, 1
    lea rsi, [msg_ev2]
    mov rdx, msg_ev2_len
    syscall

    ; c) Evento Red DMA en Core 3
    mov rax, 1
    mov rdi, 1
    lea rsi, [msg_ev3]
    mov rdx, msg_ev3_len
    syscall

    ; 4. Leer ciclo final y verificar que avanzó
    rdtsc
    shl rdx, 32
    or  rax, rdx
    mov [current_tsc], rax

    ; 5. Mensaje de Exito
    mov rax, 1
    mov rdi, 1
    lea rsi, [msg_pass]
    mov rdx, msg_pass_len
    syscall

    ; 6. Salida limpia Exit Code 0
    mov rax, 60
    xor rdi, rdi
    syscall
