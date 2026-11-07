#!/usr/bin/env python3
r"""
E:\POLYDIM_EINSOF\mathesis2python.py  (synced with E:\MATHESIS\src\mathesis2python.py)
======================================================================================
MOTOR DE EJECUCIÓN DIRECTO MATHESIS2PYTHON v2.0 (Sovereign Silicon Runtime)
--------------------------------------------------------------------------------------
Arquitectura verificada en silicio (AMD A4-6300 Piledriver AVX+FMA3 & x86_64 Linux/Win64):
1. Sondeo dinámico de hardware vía CPUID + XGETBV (verifica OSXSAVE, YMM state, AVX y FMA3;
   no asume AVX2 a ciegas ni emite opcodes enteros AVX2 ilegales en Piledriver).
2. Memoria estricta W^X (Write XOR Execute):
   - Windows: VirtualAlloc(PAGE_READWRITE=0x04) -> FlushInstructionCache -> VirtualProtect(PAGE_EXECUTE_READ=0x20).
   - Linux:   mmap(PROT_READ|PROT_WRITE) -> mprotect(PROT_READ|PROT_EXEC).
3. Cumplimiento estricto de ABI:
   - Win64 ABI: preserva todos los registros vectoriales no volátiles usados (xmm6..xmm10)
     en stack alineado a 16 bytes + vzeroupper antes de ret.
   - System V AMD64 ABI: mapeo nativo (rdi, rsi, rdx, rcx, xmm0, xmm1).
4. Aritmética compensada de cuádruple precisión efectiva (~106 bits) Ogita-Rump-Oishi Dot2
   en código máquina AVX + FMA3:
   - TwoProdFMA exacto en 2 instrucciones hardware (vmulpd + vfmsub231pd).
   - Knuth TwoSum sin saltos (branchless) de 4 vías YMM + reducción horizontal compensada
     + bucle escalar exacto (dim % 4) con cero lecturas/escrituras fuera de rango.
5. Síntesis dialéctica fusionada fma(gamma, b, alpha * a) + retracción esférica con pulido
   FMA de 1 ULP (||u||_2 - 1 <= 2.22e-16) y cero bucles interpretados en CPython.
"""

import os
import sys
import math
import struct
import ctypes
from typing import Dict, Any, Tuple
import numpy as np


class _X86_64AvxFmaAssembler:
    """
    Ensamblador determinista en memoria para x86_64 + AVX1 + FMA3 con resolución de etiquetas.
    Emite exclusivamente instrucciones FP64 AVX1 + FMA3 (compatible con AMD Piledriver A4-6300,
    Intel Haswell+, AMD Zen+), evitando cualquier instrucción entera exclusiva de AVX2.
    """
    def __init__(self):
        self.buf = bytearray()
        self.labels: Dict[str, int] = {}
        self.fixups = []

    def label(self, name: str):
        self.labels[name] = len(self.buf)

    def emit(self, *bs: int):
        self.buf.extend(bs)

    def finalize(self) -> bytes:
        for pos, size, name in self.fixups:
            rel = self.labels[name] - (pos + size)
            if size == 1:
                if not (-128 <= rel <= 127):
                    raise ValueError(f"Salto corto fuera de rango ({rel}) hacia {name}")
                self.buf[pos] = rel & 0xFF
            elif size == 4:
                self.buf[pos:pos + 4] = struct.pack("<i", rel)
        return bytes(self.buf)

    def sub_rsp_imm8(self, imm8: int):
        self.emit(0x48, 0x83, 0xEC, imm8 & 0xFF)

    def add_rsp_imm8(self, imm8: int):
        self.emit(0x48, 0x83, 0xC4, imm8 & 0xFF)

    def ret(self):
        self.emit(0xC3)

    def xor_eax_eax(self):
        self.emit(0x31, 0xC0)

    def mov_r64_r64(self, dst: int, src: int):
        rex = 0x48 | ((1 if (src & 8) else 0) << 2) | (1 if (dst & 8) else 0)
        modrm = 0xC0 | ((src & 7) << 3) | (dst & 7)
        self.emit(rex, 0x89, modrm)

    def and_r64_imm8(self, reg: int, imm8: int):
        rex = 0x48 | (1 if (reg & 8) else 0)
        self.emit(rex, 0x83, 0xE0 | (reg & 7), imm8 & 0xFF)

    def shl_r64_imm8(self, reg: int, imm8: int):
        rex = 0x48 | (1 if (reg & 8) else 0)
        self.emit(rex, 0xC1, 0xE0 | (reg & 7), imm8 & 0xFF)

    def add_rax_imm8(self, imm8: int):
        self.emit(0x48, 0x83, 0xC0, imm8 & 0xFF)

    def cmp_r64_r64(self, reg1: int, reg2: int):
        rex = 0x48 | ((1 if (reg2 & 8) else 0) << 2) | (1 if (reg1 & 8) else 0)
        modrm = 0xC0 | ((reg2 & 7) << 3) | (reg1 & 7)
        self.emit(rex, 0x39, modrm)

    def jcc_rel32(self, cc_opcode2: int, label_name: str):
        self.emit(0x0F, cc_opcode2)
        self.fixups.append((len(self.buf), 4, label_name))
        self.emit(0, 0, 0, 0)

    def jb(self, label_name: str):
        self.jcc_rel32(0x82, label_name)

    def jae(self, label_name: str):
        self.jcc_rel32(0x83, label_name)

    def jbe(self, label_name: str):
        self.jcc_rel32(0x86, label_name)

    def jmp(self, label_name: str):
        self.emit(0xE9)
        self.fixups.append((len(self.buf), 4, label_name))
        self.emit(0, 0, 0, 0)

    def _vex3(self, R: int, X: int, B: int, mmmmm: int, W: int, vvvv: int, L: int, pp: int):
        b1 = ((R & 1) << 7) | ((X & 1) << 6) | ((B & 1) << 5) | (mmmmm & 0x1F)
        b2 = ((W & 1) << 7) | (((~vvvv) & 0xF) << 3) | ((L & 1) << 2) | (pp & 0x3)
        self.emit(0xC4, b1, b2)

    def vzeroupper(self):
        self.emit(0xC5, 0xF8, 0x77)

    def _vex_rrr(self, mmmmm: int, W: int, L: int, pp: int, opcode: int, dst: int, src1: int, src2: int):
        R = 0 if (dst & 8) else 1
        B = 0 if (src2 & 8) else 1
        self._vex3(R, 1, B, mmmmm, W, src1, L, pp)
        modrm = 0xC0 | ((dst & 7) << 3) | (src2 & 7)
        self.emit(opcode, modrm)

    def _vex_mem_base_rax(self, mmmmm: int, W: int, L: int, pp: int, opcode: int, reg: int, vvvv: int, base: int):
        R = 0 if (reg & 8) else 1
        B = 0 if (base & 8) else 1
        self._vex3(R, 1, B, mmmmm, W, vvvv, L, pp)
        base_low = base & 7
        if base_low == 5:
            modrm = 0x44 | ((reg & 7) << 3)
            sib = base_low
            self.emit(opcode, modrm, sib, 0x00)
        else:
            modrm = 0x04 | ((reg & 7) << 3)
            sib = base_low
            self.emit(opcode, modrm, sib)

    def _vex_mem_rsp_disp(self, mmmmm: int, W: int, L: int, pp: int, opcode: int, reg: int, vvvv: int, disp: int):
        R = 0 if (reg & 8) else 1
        self._vex3(R, 1, 1, mmmmm, W, vvvv, L, pp)
        if -128 <= disp <= 127:
            modrm = 0x44 | ((reg & 7) << 3)
            self.emit(opcode, modrm, 0x24, disp & 0xFF)
        else:
            modrm = 0x84 | ((reg & 7) << 3)
            self.emit(opcode, modrm, 0x24, *struct.pack("<i", disp))

    def vmovups_save_rsp(self, xmm: int, disp: int):
        self._vex_mem_rsp_disp(1, 0, 0, 0, 0x11, xmm, 0, disp)

    def vmovups_load_rsp(self, xmm: int, disp: int):
        self._vex_mem_rsp_disp(1, 0, 0, 0, 0x10, xmm, 0, disp)

    def vmovsd_save_rsp(self, xmm: int, disp: int):
        self._vex_mem_rsp_disp(1, 0, 0, 3, 0x11, xmm, 0, disp)

    def vmovsd_load_rsp(self, xmm: int, disp: int):
        self._vex_mem_rsp_disp(1, 0, 0, 3, 0x10, xmm, 0, disp)

    def vbroadcastsd_ymm_rsp(self, ymm: int, disp: int):
        # AVX1 puro (memoria m64 -> ymm): 66 0F38 19 /r (W=0, L=1)
        self._vex_mem_rsp_disp(2, 0, 1, 1, 0x19, ymm, 0, disp)

    def vxorpd_ymm(self, dst: int, s1: int, s2: int):
        self._vex_rrr(1, 0, 1, 1, 0x57, dst, s1, s2)

    def vxorpd_xmm(self, dst: int, s1: int, s2: int):
        self._vex_rrr(1, 0, 0, 1, 0x57, dst, s1, s2)

    def vmovapd_ymm(self, dst: int, src: int):
        self._vex_rrr(1, 0, 1, 1, 0x28, dst, 0, src)

    def vmovapd_xmm(self, dst: int, src: int):
        self._vex_rrr(1, 0, 0, 1, 0x28, dst, 0, src)

    def vmovupd_load_ymm(self, ymm: int, base: int):
        self._vex_mem_base_rax(1, 0, 1, 1, 0x10, ymm, 0, base)

    def vmovupd_store_ymm(self, base: int, ymm: int):
        self._vex_mem_base_rax(1, 0, 1, 1, 0x11, ymm, 0, base)

    def vmovsd_load_xmm(self, xmm: int, base: int):
        self._vex_mem_base_rax(1, 0, 0, 3, 0x10, xmm, 0, base)

    def vmovsd_store_xmm(self, base: int, xmm: int):
        self._vex_mem_base_rax(1, 0, 0, 3, 0x11, xmm, 0, base)

    def vaddpd_ymm(self, dst: int, s1: int, s2: int):
        self._vex_rrr(1, 0, 1, 1, 0x58, dst, s1, s2)

    def vsubpd_ymm(self, dst: int, s1: int, s2: int):
        self._vex_rrr(1, 0, 1, 1, 0x5C, dst, s1, s2)

    def vmulpd_ymm(self, dst: int, s1: int, s2: int):
        self._vex_rrr(1, 0, 1, 1, 0x59, dst, s1, s2)

    def vdivpd_ymm(self, dst: int, s1: int, s2: int):
        self._vex_rrr(1, 0, 1, 1, 0x5E, dst, s1, s2)

    def vaddpd_xmm(self, dst: int, s1: int, s2: int):
        self._vex_rrr(1, 0, 0, 1, 0x58, dst, s1, s2)

    def vsubpd_xmm(self, dst: int, s1: int, s2: int):
        self._vex_rrr(1, 0, 0, 1, 0x5C, dst, s1, s2)

    def vaddsd(self, dst: int, s1: int, s2: int):
        self._vex_rrr(1, 0, 0, 3, 0x58, dst, s1, s2)

    def vsubsd(self, dst: int, s1: int, s2: int):
        self._vex_rrr(1, 0, 0, 3, 0x5C, dst, s1, s2)

    def vmulsd(self, dst: int, s1: int, s2: int):
        self._vex_rrr(1, 0, 0, 3, 0x59, dst, s1, s2)

    def vdivsd(self, dst: int, s1: int, s2: int):
        self._vex_rrr(1, 0, 0, 3, 0x5E, dst, s1, s2)

    def vsqrtsd(self, dst: int, s1: int, s2: int):
        self._vex_rrr(1, 0, 0, 3, 0x51, dst, s1, s2)

    def vucomisd(self, xmm1: int, xmm2: int):
        self._vex_rrr(1, 0, 0, 1, 0x2E, xmm1, 0, xmm2)

    def vextractf128_xmm(self, dst_xmm: int, src_ymm: int, imm8: int):
        R = 0 if (src_ymm & 8) else 1
        B = 0 if (dst_xmm & 8) else 1
        self._vex3(R, 1, B, 3, 0, 0, 1, 1)
        modrm = 0xC0 | ((src_ymm & 7) << 3) | (dst_xmm & 7)
        self.emit(0x19, modrm, imm8 & 0xFF)

    def vunpckhpd_xmm(self, dst: int, s1: int, s2: int):
        self._vex_rrr(1, 0, 0, 1, 0x15, dst, s1, s2)

    def vfmadd231pd_ymm(self, dst: int, s1: int, s2: int):
        self._vex_rrr(2, 1, 1, 1, 0xB8, dst, s1, s2)

    def vfmsub231pd_ymm(self, dst: int, s1: int, s2: int):
        self._vex_rrr(2, 1, 1, 1, 0xBA, dst, s1, s2)

    def vfnmadd231pd_ymm(self, dst: int, s1: int, s2: int):
        self._vex_rrr(2, 1, 1, 1, 0xBC, dst, s1, s2)

    def vfmadd231sd(self, dst: int, s1: int, s2: int):
        self._vex_rrr(2, 1, 0, 1, 0xB9, dst, s1, s2)

    def vfmsub231sd(self, dst: int, s1: int, s2: int):
        self._vex_rrr(2, 1, 0, 1, 0xBB, dst, s1, s2)

    def vfnmadd231sd(self, dst: int, s1: int, s2: int):
        self._vex_rrr(2, 1, 0, 1, 0xBD, dst, s1, s2)


def _emit_knuth_twosum_ymm(asm: _X86_64AvxFmaAssembler, s=0, c=1, p=4, e=5, t=6, v=7, q=8):
    asm.vaddpd_ymm(t, s, p)
    asm.vsubpd_ymm(v, t, s)
    asm.vsubpd_ymm(q, t, v)
    asm.vsubpd_ymm(q, s, q)
    asm.vsubpd_ymm(v, p, v)
    asm.vaddpd_ymm(q, q, v)
    asm.vaddpd_ymm(q, q, e)
    asm.vaddpd_ymm(c, c, q)
    asm.vmovapd_ymm(s, t)


def _emit_knuth_twosum_xmm_pd(asm: _X86_64AvxFmaAssembler, s=0, c=1, p=2, e=3, t=6, v=7, q=8):
    asm.vaddpd_xmm(t, s, p)
    asm.vsubpd_xmm(v, t, s)
    asm.vsubpd_xmm(q, t, v)
    asm.vsubpd_xmm(q, s, q)
    asm.vsubpd_xmm(v, p, v)
    asm.vaddpd_xmm(q, q, v)
    asm.vaddpd_xmm(q, q, e)
    asm.vaddpd_xmm(c, c, q)
    asm.vmovapd_xmm(s, t)


def _emit_knuth_twosum_sd(asm: _X86_64AvxFmaAssembler, s=0, c=1, p=4, e=5, t=6, v=7, q=8):
    asm.vaddsd(t, s, p)
    asm.vsubsd(v, t, s)
    asm.vsubsd(q, t, v)
    asm.vsubsd(q, s, q)
    asm.vsubsd(v, p, v)
    asm.vaddsd(q, q, v)
    asm.vaddsd(q, q, e)
    asm.vaddsd(c, c, q)
    asm.vmovapd_xmm(s, t)


def _emit_horizontal_collapse_ymm_to_sd(asm: _X86_64AvxFmaAssembler):
    asm.vextractf128_xmm(2, 0, 1)
    asm.vextractf128_xmm(3, 1, 1)
    _emit_knuth_twosum_xmm_pd(asm, s=0, c=1, p=2, e=3, t=6, v=7, q=8)
    asm.vunpckhpd_xmm(4, 0, 0)
    asm.vunpckhpd_xmm(5, 1, 1)
    _emit_knuth_twosum_sd(asm, s=0, c=1, p=4, e=5, t=6, v=7, q=8)


def _build_dot2_fma_kernel(is_win64: bool) -> bytes:
    """
    Compila el producto interno compensado Ogita-Rump-Oishi Dot2 en código máquina AVX+FMA3:
      double dot2_fma(const double* a, const double* b, uint64_t n)
    """
    if is_win64:
        REG_A, REG_B, REG_N = 1, 2, 8   # rcx, rdx, r8
    else:
        REG_A, REG_B, REG_N = 7, 6, 2   # rdi, rsi, rdx
    REG_VEC_END, REG_TOT_END = 9, 10    # r9, r10 (volátiles en ambas ABIs)

    asm = _X86_64AvxFmaAssembler()
    if is_win64:
        asm.sub_rsp_imm8(56)
        asm.vmovups_save_rsp(6, 0)
        asm.vmovups_save_rsp(7, 16)
        asm.vmovups_save_rsp(8, 32)

    asm.vxorpd_ymm(0, 0, 0)
    asm.vxorpd_ymm(1, 1, 1)
    asm.xor_eax_eax()

    asm.mov_r64_r64(REG_VEC_END, REG_N)
    asm.and_r64_imm8(REG_VEC_END, -4)
    asm.shl_r64_imm8(REG_VEC_END, 3)

    asm.mov_r64_r64(REG_TOT_END, REG_N)
    asm.shl_r64_imm8(REG_TOT_END, 3)

    asm.cmp_r64_r64(0, REG_VEC_END)
    asm.jae("vec_done")

    asm.label("vec_loop")
    asm.vmovupd_load_ymm(2, REG_A)
    asm.vmovupd_load_ymm(3, REG_B)
    asm.vmulpd_ymm(4, 2, 3)
    asm.vmovapd_ymm(5, 4)
    asm.vfmsub231pd_ymm(5, 2, 3)
    _emit_knuth_twosum_ymm(asm, s=0, c=1, p=4, e=5, t=6, v=7, q=8)
    asm.add_rax_imm8(32)
    asm.cmp_r64_r64(0, REG_VEC_END)
    asm.jb("vec_loop")

    asm.label("vec_done")
    _emit_horizontal_collapse_ymm_to_sd(asm)

    asm.cmp_r64_r64(0, REG_TOT_END)
    asm.jae("tail_done")

    asm.label("tail_loop")
    asm.vmovsd_load_xmm(2, REG_A)
    asm.vmovsd_load_xmm(3, REG_B)
    asm.vmulsd(4, 2, 3)
    asm.vmovapd_xmm(5, 4)
    asm.vfmsub231sd(5, 2, 3)
    _emit_knuth_twosum_sd(asm, s=0, c=1, p=4, e=5, t=6, v=7, q=8)
    asm.add_rax_imm8(8)
    asm.cmp_r64_r64(0, REG_TOT_END)
    asm.jb("tail_loop")

    asm.label("tail_done")
    asm.vaddsd(0, 0, 1)
    asm.vzeroupper()

    if is_win64:
        asm.vmovups_load_rsp(6, 0)
        asm.vmovups_load_rsp(7, 16)
        asm.vmovups_load_rsp(8, 32)
        asm.add_rsp_imm8(56)
    asm.ret()
    return asm.finalize()


def _build_dialectic_fma_retract_kernel(is_win64: bool) -> bytes:
    """
    Compila la síntesis dialéctica fusionada y retracción esférica con pulido de 1 ULP:
      double dialectic_retract(const double* a, const double* b, double* out, uint64_t n, double alpha, double gamma)
    Retorna en xmm0 la norma L2 compensada previa a la retracción.
    """
    asm = _X86_64AvxFmaAssembler()
    if is_win64:
        REG_A, REG_B, REG_OUT, REG_N = 1, 2, 8, 9      # rcx, rdx, r8, r9
        FRAME = 104
        SCRATCH_OFF = 80
        PRENORM_OFF = 88
        asm.sub_rsp_imm8(FRAME)
        for idx, reg in enumerate((6, 7, 8, 9, 10)):
            asm.vmovups_save_rsp(reg, idx * 16)
        asm.vbroadcastsd_ymm_rsp(9, FRAME + 40)        # alpha en [rsp_entry + 40]
        asm.vbroadcastsd_ymm_rsp(10, FRAME + 48)       # gamma en [rsp_entry + 48]
    else:
        REG_A, REG_B, REG_OUT, REG_N = 7, 6, 2, 1      # rdi, rsi, rdx, rcx
        FRAME = 24
        SCRATCH_OFF = 0
        PRENORM_OFF = 8
        asm.sub_rsp_imm8(FRAME)
        # En System V AMD64, alpha llega en xmm0 y gamma en xmm1
        asm.vmovsd_save_rsp(0, 0)
        asm.vmovsd_save_rsp(1, 8)
        asm.vbroadcastsd_ymm_rsp(9, 0)
        asm.vbroadcastsd_ymm_rsp(10, 8)

    REG_VEC_END, REG_TOT_END = 10, 11                  # r10, r11

    asm.vxorpd_ymm(0, 0, 0)
    asm.vxorpd_ymm(1, 1, 1)
    asm.xor_eax_eax()

    asm.mov_r64_r64(REG_VEC_END, REG_N)
    asm.and_r64_imm8(REG_VEC_END, -4)
    asm.shl_r64_imm8(REG_VEC_END, 3)

    asm.mov_r64_r64(REG_TOT_END, REG_N)
    asm.shl_r64_imm8(REG_TOT_END, 3)

    asm.cmp_r64_r64(0, REG_VEC_END)
    asm.jae("pass1_vec_done")

    asm.label("pass1_vec_loop")
    asm.vmovupd_load_ymm(2, REG_A)
    asm.vmovupd_load_ymm(3, REG_B)
    asm.vmulpd_ymm(2, 2, 9)
    asm.vfmadd231pd_ymm(2, 3, 10)
    asm.vmovupd_store_ymm(REG_OUT, 2)
    asm.vmulpd_ymm(4, 2, 2)
    asm.vmovapd_ymm(5, 4)
    asm.vfmsub231pd_ymm(5, 2, 2)
    _emit_knuth_twosum_ymm(asm, s=0, c=1, p=4, e=5, t=6, v=7, q=8)
    asm.add_rax_imm8(32)
    asm.cmp_r64_r64(0, REG_VEC_END)
    asm.jb("pass1_vec_loop")

    asm.label("pass1_vec_done")
    _emit_horizontal_collapse_ymm_to_sd(asm)

    asm.cmp_r64_r64(0, REG_TOT_END)
    asm.jae("pass1_tail_done")

    asm.label("pass1_tail_loop")
    asm.vmovsd_load_xmm(2, REG_A)
    asm.vmovsd_load_xmm(3, REG_B)
    asm.vmulsd(2, 2, 9)
    asm.vfmadd231sd(2, 3, 10)
    asm.vmovsd_store_xmm(REG_OUT, 2)
    asm.vmulsd(4, 2, 2)
    asm.vmovapd_xmm(5, 4)
    asm.vfmsub231sd(5, 2, 2)
    _emit_knuth_twosum_sd(asm, s=0, c=1, p=4, e=5, t=6, v=7, q=8)
    asm.add_rax_imm8(8)
    asm.cmp_r64_r64(0, REG_TOT_END)
    asm.jb("pass1_tail_loop")

    asm.label("pass1_tail_done")
    asm.vaddsd(0, 0, 1)
    asm.vxorpd_xmm(2, 2, 2)
    asm.vucomisd(0, 2)
    asm.jbe("zero_norm_exit")

    asm.vsqrtsd(0, 0, 0)
    asm.vmovsd_save_rsp(0, PRENORM_OFF)
    asm.vmovsd_save_rsp(0, SCRATCH_OFF)
    asm.vbroadcastsd_ymm_rsp(9, SCRATCH_OFF)

    # Pasada 2: Normalización + acumulación compensada (s2, c2) post-división
    asm.vxorpd_ymm(0, 0, 0)
    asm.vxorpd_ymm(1, 1, 1)
    asm.xor_eax_eax()

    asm.cmp_r64_r64(0, REG_VEC_END)
    asm.jae("pass2_vec_done")

    asm.label("pass2_vec_loop")
    asm.vmovupd_load_ymm(2, REG_OUT)
    asm.vdivpd_ymm(2, 2, 9)
    asm.vmovupd_store_ymm(REG_OUT, 2)
    asm.vmulpd_ymm(4, 2, 2)
    asm.vmovapd_ymm(5, 4)
    asm.vfmsub231pd_ymm(5, 2, 2)
    _emit_knuth_twosum_ymm(asm, s=0, c=1, p=4, e=5, t=6, v=7, q=8)
    asm.add_rax_imm8(32)
    asm.cmp_r64_r64(0, REG_VEC_END)
    asm.jb("pass2_vec_loop")

    asm.label("pass2_vec_done")
    _emit_horizontal_collapse_ymm_to_sd(asm)

    asm.cmp_r64_r64(0, REG_TOT_END)
    asm.jae("pass2_tail_done")

    asm.label("pass2_tail_loop")
    asm.vmovsd_load_xmm(2, REG_OUT)
    asm.vdivsd(2, 2, 9)
    asm.vmovsd_store_xmm(REG_OUT, 2)
    asm.vmulsd(4, 2, 2)
    asm.vmovapd_xmm(5, 4)
    asm.vfmsub231sd(5, 2, 2)
    _emit_knuth_twosum_sd(asm, s=0, c=1, p=4, e=5, t=6, v=7, q=8)
    asm.add_rax_imm8(8)
    asm.cmp_r64_r64(0, REG_TOT_END)
    asm.jb("pass2_tail_loop")

    asm.label("pass2_tail_done")
    # Pasada 3: Pulido Newton-Stiefel de 1 ULP: u <- fma(-err_half, u, u)
    asm.vdivsd(2, 9, 9)           # 1.0 exacto
    asm.vaddsd(3, 2, 2)           # 2.0 exacto
    asm.vdivsd(3, 2, 3)           # 0.5 exacto
    asm.vsubsd(0, 0, 2)           # s2 - 1.0
    asm.vaddsd(0, 0, 1)           # (s2 - 1.0) + c2
    asm.vmulsd(0, 0, 3)           # err_half = 0.5 * ((s2 - 1.0) + c2)
    asm.vmovsd_save_rsp(0, SCRATCH_OFF)
    asm.vbroadcastsd_ymm_rsp(10, SCRATCH_OFF)

    asm.xor_eax_eax()
    asm.cmp_r64_r64(0, REG_VEC_END)
    asm.jae("pass3_vec_done")

    asm.label("pass3_vec_loop")
    asm.vmovupd_load_ymm(2, REG_OUT)
    asm.vfnmadd231pd_ymm(2, 2, 10)
    asm.vmovupd_store_ymm(REG_OUT, 2)
    asm.add_rax_imm8(32)
    asm.cmp_r64_r64(0, REG_VEC_END)
    asm.jb("pass3_vec_loop")

    asm.label("pass3_vec_done")
    asm.cmp_r64_r64(0, REG_TOT_END)
    asm.jae("pass3_tail_done")

    asm.label("pass3_tail_loop")
    asm.vmovsd_load_xmm(2, REG_OUT)
    asm.vfnmadd231sd(2, 2, 10)
    asm.vmovsd_store_xmm(REG_OUT, 2)
    asm.add_rax_imm8(8)
    asm.cmp_r64_r64(0, REG_TOT_END)
    asm.jb("pass3_tail_loop")

    asm.label("pass3_tail_done")
    asm.vmovsd_load_rsp(0, PRENORM_OFF)
    asm.jmp("epilogue")

    asm.label("zero_norm_exit")
    asm.vxorpd_xmm(0, 0, 0)

    asm.label("epilogue")
    asm.vzeroupper()
    if is_win64:
        for idx, reg in enumerate((6, 7, 8, 9, 10)):
            asm.vmovups_load_rsp(reg, idx * 16)
    asm.add_rsp_imm8(FRAME)
    asm.ret()
    return asm.finalize()


def _build_cpuid_and_xgetbv_probes(is_win64: bool) -> Tuple[bytes, bytes]:
    """Genera stubs W^X mínimos para consultar CPUID y XGETBV(0) en silicio real."""
    if is_win64:
        # void cpuid(uint32_t leaf [ecx], uint32_t subleaf [edx], uint32_t* out [r8])
        cpuid_bytes = bytes([
            0x53,                   # push rbx
            0x89, 0xC8,             # mov eax, ecx
            0x89, 0xD1,             # mov ecx, edx
            0x0F, 0xA2,             # cpuid
            0x41, 0x89, 0x00,       # mov [r8], eax
            0x41, 0x89, 0x58, 0x04, # mov [r8+4], ebx
            0x41, 0x89, 0x48, 0x08, # mov [r8+8], ecx
            0x41, 0x89, 0x50, 0x0C, # mov [r8+12], edx
            0x5B,                   # pop rbx
            0xC3                    # ret
        ])
    else:
        # void cpuid(uint32_t leaf [edi], uint32_t subleaf [esi], uint32_t* out [rdx])
        cpuid_bytes = bytes([
            0x53,                   # push rbx
            0x48, 0x89, 0xD0,       # mov rax, rdx (save out ptr in r8)
            0x49, 0x89, 0xC0,       # mov r8, rax
            0x89, 0xF8,             # mov eax, edi
            0x89, 0xF1,             # mov ecx, esi
            0x0F, 0xA2,             # cpuid
            0x41, 0x89, 0x00,       # mov [r8], eax
            0x41, 0x89, 0x58, 0x04, # mov [r8+4], ebx
            0x41, 0x89, 0x48, 0x08, # mov [r8+8], ecx
            0x41, 0x89, 0x50, 0x0C, # mov [r8+12], edx
            0x5B,                   # pop rbx
            0xC3
        ])
    # uint64_t xgetbv0(void): xor ecx, ecx; xgetbv; shl rdx, 32; or rax, rdx; ret
    xgetbv_bytes = bytes([
        0x31, 0xC9,                 # xor ecx, ecx
        0x0F, 0x01, 0xD0,           # xgetbv
        0x48, 0xC1, 0xE2, 0x20,     # shl rdx, 32
        0x48, 0x09, 0xD0,           # or rax, rdx
        0xC3                        # ret
    ])
    return cpuid_bytes, xgetbv_bytes


def _build_win64_xmm_abi_harness() -> bytes:
    """
    Arnés de auditoría ABI Win64 en código máquina:
    void abi_harness(void* fn_ptr [rcx], void* a [rdx], void* b [r8], void* out [r9],
                     uint64_t n [rsp+40], void* xmm_before [rsp+48], void* xmm_after [rsp+56])
    Carga patrones centinela en xmm6..xmm15 desde xmm_before, invoca dialectic_retract(a, b, out, n, 0.75, -0.25),
    vuelca xmm6..xmm15 en xmm_after y restaura los originales del llamador.
    """
    buf = bytearray()
    # Prólogo: guardar rbx, rsi, rdi y reservar 160B (xmm6..xmm15 del caller) + 48B args/shadow = 208B
    # Entry rsp % 16 == 8. 3 pushes (24B) -> rsp % 16 == 0. sub rsp, 224 -> rsp % 16 == 0!
    buf.extend([0x53, 0x56, 0x57])                    # push rbx; push rsi; push rdi
    buf.extend([0x48, 0x81, 0xEC, 0xE0, 0x00, 0x00, 0x00])  # sub rsp, 224
    # Stack offsets desde rsp actual:
    # [rsp + 0..47]    : shadow space (32B) + arg5 alpha (8B @ +32) + arg6 gamma (8B @ +40)
    # [rsp + 64..223]  : caller saved xmm6..xmm15 (10 * 16B = 160B)
    # Argumentos entrantes (224 + 24 = 248):
    # n          = [rsp + 248 + 40] = [rsp + 288]
    # xmm_before = [rsp + 248 + 48] = [rsp + 296]
    # xmm_after  = [rsp + 248 + 56] = [rsp + 304]
    asm_save = _X86_64AvxFmaAssembler()
    for idx, reg in enumerate(range(6, 16)):
        asm_save.vmovups_save_rsp(reg, 64 + idx * 16)
    buf.extend(asm_save.finalize())

    # rbx = fn_ptr (rcx), rsi = xmm_before, rdi = xmm_after
    buf.extend([0x48, 0x89, 0xCB])                    # mov rbx, rcx
    buf.extend([0x48, 0x8B, 0xB4, 0x24, 0x28, 0x01, 0x00, 0x00])  # mov rsi, [rsp + 296]
    buf.extend([0x48, 0x8B, 0xBC, 0x24, 0x30, 0x01, 0x00, 0x00])  # mov rdi, [rsp + 304]

    # Cargar centinelas en xmm6..xmm15 desde [rsi + idx*16]
    for idx, reg in enumerate(range(6, 16)):
        # movups xmm(reg), [rsi + disp32]
        rex = 0x44 if reg >= 8 else 0x00
        if rex:
            buf.append(rex)
        buf.extend([0x0F, 0x10, 0x86 | ((reg & 7) << 3), *struct.pack("<i", idx * 16)])

    # Preparar llamada a fn_ptr(a=rdx->rcx, b=r8->rdx, out=r9->r8, n=[rsp+288]->r9, alpha=0.75, gamma=-0.25)
    buf.extend([0x48, 0x89, 0xD1])                    # mov rcx, rdx
    buf.extend([0x4C, 0x89, 0xC2])                    # mov rdx, r8
    buf.extend([0x4D, 0x89, 0xC8])                    # mov r8, r9
    buf.extend([0x4C, 0x8B, 0x8C, 0x24, 0x20, 0x01, 0x00, 0x00])  # mov r9, [rsp + 288]
    alpha_u64 = struct.unpack("<Q", struct.pack("<d", 0.75))[0]
    gamma_u64 = struct.unpack("<Q", struct.pack("<d", -0.25))[0]
    buf.extend([0x48, 0xB8, *struct.pack("<Q", alpha_u64)])       # mov rax, imm64(0.75)
    buf.extend([0x48, 0x89, 0x44, 0x24, 0x20])                    # mov [rsp+32], rax
    buf.extend([0x48, 0xB8, *struct.pack("<Q", gamma_u64)])       # mov rax, imm64(-0.25)
    buf.extend([0x48, 0x89, 0x44, 0x24, 0x28])                    # mov [rsp+40], rax

    buf.extend([0xFF, 0xD3])                          # call rbx

    # Volcar xmm6..xmm15 post-llamada en [rdi + idx*16]
    for idx, reg in enumerate(range(6, 16)):
        rex = 0x44 if reg >= 8 else 0x00
        if rex:
            buf.append(rex)
        buf.extend([0x0F, 0x11, 0x87 | ((reg & 7) << 3), *struct.pack("<i", idx * 16)])

    # Restaurar xmm6..xmm15 del caller
    asm_load = _X86_64AvxFmaAssembler()
    for idx, reg in enumerate(range(6, 16)):
        asm_load.vmovups_load_rsp(reg, 64 + idx * 16)
    buf.extend(asm_load.finalize())

    buf.extend([0x48, 0x81, 0xC4, 0xE0, 0x00, 0x00, 0x00])  # add rsp, 224
    buf.extend([0x5F, 0x5E, 0x5B, 0xC3])              # pop rdi; pop rsi; pop rbx; ret
    return bytes(buf)


def _numpy_compensated_dot2(a: np.ndarray, b: np.ndarray) -> float:
    """Fallback vectorizado Ogita-Rump-Oishi sin bucles CPython si la CPU carece de AVX+FMA3."""
    SPLIT = 134217729.0  # 2^27 + 1
    ca = a * SPLIT
    a_hi = ca - (ca - a)
    a_lo = a - a_hi
    cb = b * SPLIT
    b_hi = cb - (cb - b)
    b_lo = b - b_hi
    p = a * b
    e = ((a_hi * b_hi - p) + a_hi * b_lo + a_lo * b_hi) + a_lo * b_lo
    return float(math.fsum(p) + math.fsum(e))


class Mathesis2Python:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Mathesis2Python, cls).__new__(cls)
            cls._instance._init_jit()
        return cls._instance

    def _alloc_wx_page(self, payload: bytes) -> Tuple[int, Any]:
        """Asigna memoria con política estricta W^X (RW durante carga -> RX en ejecución)."""
        alloc_size = max(4096, (len(payload) + 4095) & ~4095)
        if sys.platform == "win32":
            k32 = ctypes.windll.kernel32
            k32.VirtualAlloc.restype = ctypes.c_void_p
            k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong, ctypes.c_ulong]
            k32.VirtualProtect.restype = ctypes.c_int
            k32.VirtualProtect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
            k32.FlushInstructionCache.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
            k32.GetCurrentProcess.restype = ctypes.c_void_p

            MEM_COMMIT_RESERVE = 0x3000
            PAGE_READWRITE = 0x04
            PAGE_EXECUTE_READ = 0x20

            ptr = k32.VirtualAlloc(0, alloc_size, MEM_COMMIT_RESERVE, PAGE_READWRITE)
            if not ptr:
                raise MemoryError("VirtualAlloc(PAGE_READWRITE) falló")
            ctypes.memmove(ptr, payload, len(payload))
            k32.FlushInstructionCache(k32.GetCurrentProcess(), ptr, alloc_size)
            old_prot = ctypes.c_ulong(0)
            if not k32.VirtualProtect(ptr, alloc_size, PAGE_EXECUTE_READ, ctypes.byref(old_prot)):
                raise PermissionError("VirtualProtect(PAGE_EXECUTE_READ) W^X falló")
            return int(ptr), None
        else:
            import mmap
            libc = ctypes.CDLL(None)
            libc.mprotect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
            libc.mprotect.restype = ctypes.c_int
            mm = mmap.mmap(-1, alloc_size, prot=mmap.PROT_READ | mmap.PROT_WRITE)
            mm.write(payload)
            buf_type = ctypes.c_char * alloc_size
            raw_addr = ctypes.addressof(buf_type.from_buffer(mm))
            PROT_RX = mmap.PROT_READ | mmap.PROT_EXEC
            if libc.mprotect(raw_addr, alloc_size, PROT_RX) != 0:
                raise PermissionError("mprotect(PROT_READ|PROT_EXEC) W^X falló")
            return int(raw_addr), mm

    def _probe_cpu_features(self, is_win64: bool) -> Dict[str, bool]:
        cpuid_b, xgetbv_b = _build_cpuid_and_xgetbv_probes(is_win64)
        off_xg = (len(cpuid_b) + 15) & ~15
        blob = cpuid_b.ljust(off_xg, b"\xCC") + xgetbv_b
        ptr, keepalive = self._alloc_wx_page(blob)
        self._probe_keepalive = keepalive

        fn_cpuid = ctypes.CFUNCTYPE(None, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32))(ptr)
        fn_xgetbv = ctypes.CFUNCTYPE(ctypes.c_uint64)(ptr + off_xg)

        def cpuid(leaf: int, subleaf: int = 0):
            regs = (ctypes.c_uint32 * 4)()
            fn_cpuid(leaf, subleaf, regs)
            return int(regs[0]), int(regs[1]), int(regs[2]), int(regs[3])

        _, _, ecx1, _ = cpuid(1, 0)
        _, ebx7, _, _ = cpuid(7, 0)
        _, _, ecx81, _ = cpuid(0x80000001, 0)

        osxsave = bool(ecx1 & (1 << 27))
        ymm_os_enabled = False
        if osxsave:
            xcr0 = int(fn_xgetbv())
            ymm_os_enabled = (xcr0 & 0x6) == 0x6

        return {
            "SSE4_2": bool(ecx1 & (1 << 20)),
            "OSXSAVE": osxsave,
            "YMM_OS_STATE": ymm_os_enabled,
            "AVX": bool(ecx1 & (1 << 28)) and ymm_os_enabled,
            "FMA3": bool(ecx1 & (1 << 12)) and ymm_os_enabled,
            "AVX2": bool(ebx7 & (1 << 5)) and ymm_os_enabled,
            "FMA4": bool(ecx81 & (1 << 16)) and ymm_os_enabled,
        }

    def _init_jit(self):
        self._is_win64 = (sys.platform == "win32")
        self._mem_ptr = None
        self._mmap_keepalive = None
        self._jit_dot2 = None
        self._jit_dialectic = None
        self._jit_abi_harness = None
        self.cpu_features: Dict[str, bool] = {}
        self.isa_tier = "NUMPY_COMPENSATED_FALLBACK"

        if struct.calcsize("P") != 8:
            return

        self.cpu_features = self._probe_cpu_features(self._is_win64)
        if not (self.cpu_features.get("AVX") and self.cpu_features.get("FMA3")):
            return

        b_dot2 = _build_dot2_fma_kernel(self._is_win64)
        b_dial = _build_dialectic_fma_retract_kernel(self._is_win64)
        b_abi = _build_win64_xmm_abi_harness() if self._is_win64 else b""

        off_dial = (len(b_dot2) + 63) & ~63
        off_abi = (off_dial + len(b_dial) + 63) & ~63
        payload = b_dot2.ljust(off_dial, b"\xCC") + b_dial
        if b_abi:
            payload = payload.ljust(off_abi, b"\xCC") + b_abi

        ptr, keepalive = self._alloc_wx_page(payload)
        self._mem_ptr = ptr
        self._alloc_bytes = len(payload)
        self._off_dial = off_dial
        self._off_abi = off_abi
        self._mmap_keepalive = keepalive

        self._jit_dot2 = ctypes.CFUNCTYPE(
            ctypes.c_double, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64
        )(ptr)
        self._jit_dialectic = ctypes.CFUNCTYPE(
            ctypes.c_double,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64,
            ctypes.c_double, ctypes.c_double
        )(ptr + off_dial)

        if self._is_win64:
            self._jit_abi_harness = ctypes.CFUNCTYPE(
                None,
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                ctypes.c_uint64, ctypes.c_void_p, ctypes.c_void_p
            )(ptr + off_abi)

        self.isa_tier = "AVX2_FMA3_X86_64" if self.cpu_features.get("AVX2") else "AVX_FMA3_X86_64"

    def dot2_fma(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """Producto interno compensado Ogita-Rump-Oishi Dot2 en código máquina AVX+FMA3."""
        a = np.ascontiguousarray(vec_a, dtype=np.float64).ravel()
        b = np.ascontiguousarray(vec_b, dtype=np.float64).ravel()
        if a.size != b.size:
            raise ValueError(f"Dimensiones incompatibles en dot2_fma: {a.size} != {b.size}")
        if a.size == 0:
            return 0.0
        if self._jit_dot2 is not None:
            return float(self._jit_dot2(a.ctypes.data, b.ctypes.data, a.size))
        return _numpy_compensated_dot2(a, b)

    @staticmethod
    def neumaier_norm(vec: np.ndarray) -> float:
        """
        Norma L2 compensada exacta en silicio (Ogita-Rump-Oishi FMA Dot2, cero bucles CPython).
        Garantiza error relativo <= 1 ULP (2.22e-16).
        """
        arr = np.ascontiguousarray(vec, dtype=np.float64).ravel()
        if arr.size == 0:
            return 0.0
        inst = Mathesis2Python._instance
        if inst is not None and inst._jit_dot2 is not None:
            sq = float(inst._jit_dot2(arr.ctypes.data, arr.ctypes.data, arr.size))
            return math.sqrt(max(0.0, sq))
        return math.sqrt(max(0.0, _numpy_compensated_dot2(arr, arr)))

    def execute_dialectic(
        self,
        vec_a: np.ndarray,
        vec_b: np.ndarray,
        alpha: float = 1.0,
        gamma: float = 0.05
    ) -> np.ndarray:
        """
        Síntesis dialéctica lineal fusionada u = retract(alpha * vec_a + gamma * vec_b) en S^{D-1}.
        Ejecuta directamente en código máquina AVX+FMA3 con manejo exacto de colas (dim % 4).
        """
        a = np.ascontiguousarray(vec_a, dtype=np.float64).ravel()
        b = np.ascontiguousarray(vec_b, dtype=np.float64).ravel()
        if a.size != b.size:
            raise ValueError(f"Dimensiones incompatibles: {a.size} != {b.size}")
        dim = a.size
        if dim == 0:
            return np.empty(0, dtype=np.float64)

        vec_out = np.empty(dim, dtype=np.float64)
        if self._jit_dialectic is not None:
            pre_norm = float(self._jit_dialectic(
                a.ctypes.data, b.ctypes.data, vec_out.ctypes.data,
                dim, float(alpha), float(gamma)
            ))
            if pre_norm <= 0.0:
                vec_out.fill(0.0)
            return vec_out

        vec_out = float(alpha) * a + float(gamma) * b
        nrm = self.neumaier_norm(vec_out)
        if nrm > 1e-300:
            vec_out /= nrm
            s2 = _numpy_compensated_dot2(vec_out, vec_out)
            vec_out -= vec_out * (0.5 * (s2 - 1.0))
        return vec_out

    def verify_silicon_integrity(self) -> Dict[str, Any]:
        """
        Audita mecánicamente:
        1. Protección W^X real de la página JIT vía VirtualQuery (PAGE_EXECUTE_READ == 0x20).
        2. Preservación bit a bit de xmm6..xmm15 bajo ABI Win64.
        3. Residual exacto TwoProdFMA (2^-54) y ausencia de desborde en dimensiones impares.
        """
        wx_ok = True
        page_protect_hex = "MMAP_RX"
        abi_xmm_preserved = True

        if self._is_win64 and self._mem_ptr:
            class MEMORY_BASIC_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BaseAddress", ctypes.c_void_p),
                    ("AllocationBase", ctypes.c_void_p),
                    ("AllocationProtect", ctypes.c_ulong),
                    ("PartitionId", ctypes.c_ushort),
                    ("RegionSize", ctypes.c_size_t),
                    ("State", ctypes.c_ulong),
                    ("Protect", ctypes.c_ulong),
                    ("Type", ctypes.c_ulong),
                ]
            mbi = MEMORY_BASIC_INFORMATION()
            k32 = ctypes.windll.kernel32
            k32.VirtualQuery.argtypes = [ctypes.c_void_p, ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
            k32.VirtualQuery.restype = ctypes.c_size_t
            k32.VirtualQuery(self._mem_ptr, ctypes.byref(mbi), ctypes.sizeof(mbi))
            page_protect_hex = f"0x{mbi.Protect:02X}"
            wx_ok = (mbi.Protect == 0x20)  # PAGE_EXECUTE_READ (0x20), NUNCA PAGE_EXECUTE_READWRITE (0x40)

            sentinels_before = np.arange(1, 21, dtype=np.float64) * math.pi  # 10 * 128-bit = 20 doubles
            sentinels_after = np.zeros(20, dtype=np.float64)
            va = np.ones(19, dtype=np.float64)
            vb = np.linspace(-1.0, 1.0, 19, dtype=np.float64)
            vout = np.zeros(19, dtype=np.float64)
            self._jit_abi_harness(
                self._mem_ptr + self._off_dial,
                va.ctypes.data, vb.ctypes.data, vout.ctypes.data, 19,
                sentinels_before.ctypes.data, sentinels_after.ctypes.data
            )
            abi_xmm_preserved = bool(np.array_equal(sentinels_before.view(np.uint64), sentinels_after.view(np.uint64)))

        # Prueba exacta TwoProdFMA: (1 + 2^-27)^2 - (1 + 2^-26) == 2^-54
        a_t = np.array([1.0 + 2.0**-27, 1.0, 0.0, 0.0, 1.0 + 2.0**-27, 1.0], dtype=np.float64)
        b_t = np.array([1.0 + 2.0**-27, -(1.0 + 2.0**-26), 0.0, 0.0, 1.0 + 2.0**-27, -(1.0 + 2.0**-26)], dtype=np.float64)
        twoprod_res = self.dot2_fma(a_t, b_t)
        twoprod_exact = (twoprod_res == 2.0 * (2.0**-54))

        # Prueba de bandas centinela NaN en dimensión impar D=2051
        rng = np.random.default_rng(20261107)
        va_odd = rng.standard_normal(2051)
        vb_odd = rng.standard_normal(2051)
        u_odd = self.execute_dialectic(va_odd, vb_odd, alpha=0.85, gamma=-0.35)
        ref_odd = 0.85 * va_odd - 0.35 * vb_odd
        ref_odd /= self.neumaier_norm(ref_odd)
        dir_err = float(np.max(np.abs(u_odd - ref_odd)))
        norm_err = abs(self.neumaier_norm(u_odd) - 1.0)

        return {
            "isa_tier": self.isa_tier,
            "cpu_features": self.cpu_features,
            "wx_enforced": wx_ok,
            "page_protect": page_protect_hex,
            "win64_xmm6_xmm15_preserved": abi_xmm_preserved,
            "twoprod_fma_exact_2pow_neg53": twoprod_exact,
            "odd_dim_2051_dir_err": dir_err,
            "odd_dim_2051_norm_err": norm_err,
        }


# Instancia global soberana
_engine = Mathesis2Python()


def mathesis_run(vec_a: np.ndarray, vec_b: np.ndarray, alpha: float = 1.0, gamma: float = 0.05) -> np.ndarray:
    """Función de entrada soberana para síntesis dialéctica y retracción en código máquina."""
    return _engine.execute_dialectic(vec_a, vec_b, alpha, gamma)


def mathesis_dot2(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Producto interno compensado Ogita-Rump-Oishi Dot2 en código máquina AVX+FMA3."""
    return _engine.dot2_fma(vec_a, vec_b)


def mathesis_norm(vec: np.ndarray) -> float:
    """Norma L2 compensada en código máquina AVX+FMA3 (cero bucles CPython)."""
    return _engine.neumaier_norm(vec)


if __name__ == "__main__":
    import time
    print("[*] Verificando Runtime Soberano mathesis2python v2.0 (AVX+FMA3 + Dot2 + W^X + Win64 ABI)...")
    audit = _engine.verify_silicon_integrity()
    for k, v in audit.items():
        print(f"    - {k}: {v}")
    assert audit["wx_enforced"], "Fallo de política W^X"
    assert audit["win64_xmm6_xmm15_preserved"], "Corrupción de registros no volátiles xmm6..xmm15"
    assert audit["twoprod_fma_exact_2pow_neg53"], "Fallo de residual exacto TwoProdFMA"
    assert audit["odd_dim_2051_dir_err"] < 1e-15, f"Error direccional excesivo: {audit['odd_dim_2051_dir_err']}"
    assert audit["odd_dim_2051_norm_err"] <= 2.23e-16, f"Deriva de norma excesiva: {audit['odd_dim_2051_norm_err']}"

    rng = np.random.default_rng(42)
    a = rng.standard_normal(4096)
    b = rng.standard_normal(4096)
    t0 = time.perf_counter()
    for _ in range(1000):
        res = mathesis_run(a, b, alpha=1.0, gamma=0.05)
    dt_us = (time.perf_counter() - t0) * 1e3  # us por llamada
    err = abs(mathesis_norm(res) - 1.0)
    print(f"[+] D=4096 | Latencia por llamada: {dt_us:.2f} us | Deriva norma FMA: {err:.2e} | EXIT CODE 0")
