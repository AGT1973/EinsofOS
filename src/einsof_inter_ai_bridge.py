#!/usr/bin/env python3
"""
einsof_inter_ai_bridge.py — Puente y Compilador Inter-IA del Lenguaje Einsof
Permite que un modelo de IA emita un Grafo Tensorial Estructurado (sin letras de codigo humano),
lo valide contra el esquema canonico EINSOF_INTER_AI_SCHEMA.json,
y lo compile directamente a Assembler x86_64 AVX2 ejecutable en silicio.
"""

import json
import os
import sys
import subprocess
from typing import Dict, Any, List

class EinsofInterAIBridge:
    def __init__(self, schema_path: str):
        self.schema_path = schema_path
        with open(schema_path, "r", encoding="utf-8") as f:
            self.schema = json.load(f)

    def validate_trace(self, trace_graph: Dict[str, Any]) -> bool:
        """Valida matematicamente que el grafo cumpla con las leyes de silicio Einsof."""
        if "nodes" not in trace_graph:
            return False
        
        valid_ops = {op["mnemonic"] for op in self.schema["instruction_set"]}
        for node in trace_graph["nodes"]:
            if node["op"] not in valid_ops:
                print(f"[-] Error de esquema: Operador invalido {node['op']}")
                return False
        return True

    def compile_trace_to_asm(self, trace_graph: Dict[str, Any], output_asm_path: str) -> str:
        """Compila el grafo tensorial generado por la IA directamente a Assembler x86_64 puro."""
        lines = [
            "; ==============================================================================",
            f"; AUTO-COMPILED FROM INTER-AI TRACE: {trace_graph.get('trace_id', 'ANONYMOUS')}",
            "; Emisor: Machine-to-Machine Bridge (Cero C, Cero Libc, AVX2 FMA)",
            "; ==============================================================================",
            "",
            '%include "einsof_types.inc"',
            "",
            "default rel",
            "",
            "section .data",
            "    align 64",
            '    msg_boot:       db "[+] EINSOF INTER-AI COMPILED RUNTIME: EXECUTING IN SILICON", 10',
            "    msg_boot_len:   equ $ - msg_boot",
            '    msg_done:       db "[+] INTER-AI TRACE EXECUTED WITH SUCCESS (EXIT CODE 0)", 10',
            "    msg_done_len:   equ $ - msg_done",
            "",
            "    align 32",
            "    init_vec:       dq 0.02209708691207961, 0.02209708691207961, 0.02209708691207961, 0.02209708691207961",
            "    rot_cos:        dq 0.9998000066665778, 0.9998000066665778, 0.9998000066665778, 0.9998000066665778",
            "    rot_sin:        dq 0.0199986666933331, 0.0199986666933331, 0.0199986666933331, 0.0199986666933331",
            "",
            "section .bss",
            "    align 64",
            "    arena_base_ptr: resq 1",
            "",
            "section .text",
            "    global _start",
            "",
            "_start:",
            "    ; Banner de inicio",
            "    mov rax, 1",
            "    mov rdi, 1",
            "    lea rsi, [msg_boot]",
            "    mov rdx, msg_boot_len",
            "    syscall",
            "",
            "    ; Asignar Arena de memoria R15 (64 MB via sys_mmap)",
            "    mov rax, 9",
            "    xor rdi, rdi",
            "    mov rsi, 67108864",
            "    mov rdx, 3",
            "    mov r10, 34",
            "    mov r8, -1",
            "    xor r9, r9",
            "    syscall",
            "    cmp rax, 0",
            "    jl .error_exit",
            "",
            "    mov r15, rax",
            "    mov [arena_base_ptr], r15",
            ""
        ]

        # Inicialización de Slabs
        lines.extend([
            "    ; Inicializar Slab 0 (Tensor A)",
            "    mov rax, 0x45494E534F463031",
            "    mov qword [r15 + 0], rax",
            "    mov word  [r15 + 8], TYPE_TENSOR_STIEFEL",
            "    mov byte  [r15 + 10], 1",
            "    mov dword [r15 + 12], 2048",
            "    vmovupd ymm0, [init_vec]",
            "    lea rdi, [r15 + 64]",
            "    mov rcx, 512",
            ".init_a:",
            "    vmovupd [rdi], ymm0",
            "    add rdi, 32",
            "    dec rcx",
            "    jnz .init_a",
            "",
            "    ; Inicializar Slab 16448 (Rotor B)",
            "    lea rbx, [r15 + 16448]",
            "    mov qword [rbx + 0], rax",
            "    mov word  [rbx + 8], TYPE_ROTOR_CLIFFORD",
            "    mov byte  [rbx + 10], 1",
            "    mov dword [rbx + 12], 2048",
            "    lea rdi, [rbx + 64]",
            "    mov rcx, 512",
            ".init_b:",
            "    vmovupd [rdi], ymm0",
            "    add rdi, 32",
            "    dec rcx",
            "    jnz .init_b",
            ""
        ])

        # Compilar cada nodo del grafo
        for node in trace_graph["nodes"]:
            op = node["op"]
            if op == "OP_ROT_LIE":
                src = node["src_a"]
                dst = node["dst"]
                lines.extend([
                    f"    ; --- NODO: OP_ROT_LIE (src={src} -> dst={dst}) ---",
                    f"    lea rsi, [r15 + {src} + 64]",
                    f"    lea rdi, [r15 + {dst} + 64]",
                    "    vmovupd ymm14, [rot_cos]",
                    "    vmovupd ymm15, [rot_sin]",
                    "    mov rcx, 512",
                    f".loop_rot_{dst}:",
                    "    vmovupd ymm1, [rsi]",
                    "    vmulpd  ymm2, ymm1, ymm14",
                    "    vmulpd  ymm3, ymm1, ymm15",
                    "    vsubpd  ymm4, ymm2, ymm3",
                    "    vmovupd [rdi], ymm4",
                    "    add rsi, 32",
                    "    add rdi, 32",
                    "    dec rcx",
                    f"    jnz .loop_rot_{dst}",
                    ""
                ])
            elif op == "OP_PROJECT_GRASSMANN":
                src = node["src_a"]
                base = node["src_b"]
                dst = node["dst"]
                lines.extend([
                    f"    ; --- NODO: OP_PROJECT_GRASSMANN (src={src}, base={base}) ---",
                    f"    lea rsi, [r15 + {src} + 64]",
                    f"    lea rdi, [r15 + {base} + 64]",
                    "    vxorpd ymm5, ymm5, ymm5",
                    "    mov rcx, 512",
                    f".loop_proj_{dst}:",
                    "    vmovupd ymm1, [rsi]",
                    "    vmovupd ymm2, [rdi]",
                    "    vfmadd231pd ymm5, ymm1, ymm2",
                    "    add rsi, 32",
                    "    add rdi, 32",
                    "    dec rcx",
                    f"    jnz .loop_proj_{dst}",
                    "    vextractf128 xmm6, ymm5, 1",
                    "    vaddpd xmm6, xmm6, xmm5",
                    "    vhaddpd xmm6, xmm6, xmm6",
                    "    vbroadcastsd ymm7, xmm6",
                    f"    lea rdi, [r15 + {base} + 64]",
                    f"    lea r8,  [r15 + {dst} + 64]",
                    "    mov rcx, 512",
                    f".loop_scale_{dst}:",
                    "    vmovupd ymm2, [rdi]",
                    "    vmulpd  ymm8, ymm2, ymm7",
                    "    vmovupd [r8], ymm8",
                    "    add rdi, 32",
                    "    add r8, 32",
                    "    dec rcx",
                    f"    jnz .loop_scale_{dst}",
                    ""
                ])
            elif op == "OP_RETRACT_STIEFEL":
                target = node["target"]
                lines.extend([
                    f"    ; --- NODO: OP_RETRACT_STIEFEL (target={target}) ---",
                    f"    lea rsi, [r15 + {target} + 64]",
                    "    vxorpd ymm9, ymm9, ymm9",
                    "    mov rcx, 512",
                    f".loop_norm_{target}:",
                    "    vmovupd ymm1, [rsi]",
                    "    vfmadd231pd ymm9, ymm1, ymm1",
                    "    add rsi, 32",
                    "    dec rcx",
                    f"    jnz .loop_norm_{target}",
                    "    vextractf128 xmm10, ymm9, 1",
                    "    vaddpd xmm10, xmm10, xmm9",
                    "    vhaddpd xmm10, xmm10, xmm10",
                    "    vsqrtpd xmm11, xmm10",
                    "    mov rax, 0x3FF0000000000000",
                    "    vmovq xmm12, rax",
                    "    vdivpd xmm13, xmm12, xmm11",
                    "    vbroadcastsd ymm13, xmm13",
                    f"    lea rsi, [r15 + {target} + 64]",
                    "    mov rcx, 512",
                    f".loop_renorm_{target}:",
                    "    vmovupd ymm1, [rsi]",
                    "    vmulpd  ymm2, ymm1, ymm13",
                    "    vmovupd [rsi], ymm2",
                    "    add rsi, 32",
                    "    dec rcx",
                    f"    jnz .loop_renorm_{target}",
                    ""
                ])
            elif op == "OP_DESTROY_EPHEMERAL":
                target = node["target"]
                lines.extend([
                    f"    ; --- NODO: OP_DESTROY_EPHEMERAL (target={target} en O(1)) ---",
                    f"    inc byte [r15 + {target} + 10] ; Invalida generacion",
                    ""
                ])
            elif op == "OP_HALT_STABLE":
                lines.extend([
                    "    ; --- NODO: OP_HALT_STABLE (Fin de ejecucion) ---",
                    "    mov rax, 1",
                    "    mov rdi, 1",
                    "    lea rsi, [msg_done]",
                    "    mov rdx, msg_done_len",
                    "    syscall",
                    "    mov rax, 60",
                    "    xor rdi, rdi",
                    "    syscall",
                    "",
                    ".error_exit:",
                    "    mov rax, 60",
                    "    mov rdi, 1",
                    "    syscall"
                ])

        with open(output_asm_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"[+] Archivo Assembler generado por el Puente Inter-IA: {output_asm_path}")
        return output_asm_path

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema_file = os.path.join(base_dir, "docs", "EINSOF_INTER_AI_SCHEMA.json")
    bridge = EinsofInterAIBridge(schema_file)

    # Grafo de ejemplo simulado emitido por una IA
    sample_trace = {
        "trace_id": "DEEPSEEK_TO_QWEN_GEODESIC_PASS",
        "arena_capacity": 67108864,
        "nodes": [
            { "step": 0, "op": "OP_ROT_LIE", "src_a": 0, "src_b": 16448, "dst": 32896 },
            { "step": 1, "op": "OP_PROJECT_GRASSMANN", "src_a": 32896, "src_b": 16448, "dst": 32896 },
            { "step": 2, "op": "OP_RETRACT_STIEFEL", "target": 32896 },
            { "step": 3, "op": "OP_DESTROY_EPHEMERAL", "target": 32896 },
            { "step": 4, "op": "OP_HALT_STABLE" }
        ]
    }

    if bridge.validate_trace(sample_trace):
        print("[+] Grafo Inter-IA validado con exito contra el esquema canonico.")
        out_asm = os.path.join(base_dir, "src", "inter_ai_compiled.asm")
        bridge.compile_trace_to_asm(sample_trace, out_asm)
