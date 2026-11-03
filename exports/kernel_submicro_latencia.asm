; Auto-generado por EinsofOS Polyglot Exporter para kernel_submicro_latencia
; Tarea: Rutina bare-metal de maxima velocidad en silicio puro -> Lenguaje optimo: ASSEMBLER X86_64 PURO (Latencia sub-microsegundo)
%include "einsof_types.inc"
default rel
section .text
global _start
_start:
    mov rax, 60
    xor rdi, rdi
    syscall
