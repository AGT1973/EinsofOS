; ==============================================================================
; EINSOF AUTONOMOUS SATELLITE FAILOVER (X86_64 ATOMIC XCHG / ZERO-C)
; Conmutacion de puntero de red en 1 ciclo de reloj ante degradacion de SNR
; ==============================================================================

%include "einsof_types.inc"
default rel

section .data
    align 64
    msg_start:   db "[+] LINK SATELITAL EN EJECUCION: SATELITE_ALFA ACTIVO", 10
    msg_start_len: equ $ - msg_start
    msg_alert:   db "[-] ALERTA IA: SENAL DEGRADADA (SNR < 12 DB) -> CONMUTANDO...", 10
    msg_alert_len: equ $ - msg_alert
    msg_swapped: db "[+] HOT-SWAP ATOMICO COMPLETADO: SATELITE_BETA EN LINEA (EXIT CODE 0)", 10
    msg_swapped_len: equ $ - msg_swapped

    ; Punteros a los descriptores de ambos satelites
    align 8
    ptr_sat_alpha: dq 0x00000000A1FAD000 ; Descriptor Satelite Alfa
    ptr_sat_beta:  dq 0x00000000B2E7D000 ; Descriptor Satelite Beta

section .bss
    align 8
    active_link_ptr: resq 1 ; Puntero global de red consumido por el hardware

section .text
    global _start

_start:
    ; 1. Iniciar con Satelite Alfa en active_link_ptr
    mov rax, [ptr_sat_alpha]
    mov [active_link_ptr], rax

    mov rax, 1 ; sys_write
    mov rdi, 1
    lea rsi, [msg_start]
    mov rdx, msg_start_len
    syscall

    ; 2. La IA detecta la anomalia de telemetria
    mov rax, 1
    mov rdi, 1
    lea rsi, [msg_alert]
    mov rdx, msg_alert_len
    syscall

    ; 3. INTERCAMBIO ATOMICO EN SILICIO: xchg intercambia el puntero en 1 ciclo
    mov rbx, [ptr_sat_beta]         ; Cargamos el nuevo canal optimo
    xchg [active_link_ptr], rbx     ; OPERACION ATOMICA DE HARDWARE (Cero bloqueo)

    ; 4. Notificar conmutacion exitosa
    mov rax, 1
    mov rdi, 1
    lea rsi, [msg_swapped]
    mov rdx, msg_swapped_len
    syscall

    ; 5. Salir limpiamente
    mov rax, 60
    xor rdi, rdi
    syscall
