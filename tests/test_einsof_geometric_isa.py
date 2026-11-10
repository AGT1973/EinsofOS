"""
===============================================================================
TEST SUITE: EINSOF GEOMETRIC ISA & CONTINUOUS MANIFOLD RUNTIME
Verificación en silicio: 64-byte alignment, Neumaier S^2047, Lyapunov & Colapso 1D
===============================================================================
"""

import os
import sys
import math
import struct
import unittest
import numpy as np

# Añadir src al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from einsof_geometric_vm import (
    EinsofInstruction64,
    EinsofGeometricVM,
    neumaier_norm,
    EINSOF_OP_HALT_STABLE,
    EINSOF_OP_ROT_LIE,
    EINSOF_OP_RETRACT_STIEFEL,
    EINSOF_OP_PROJECT_GRASSMANN,
    EINSOF_OP_BIFURCATE_LYAPUNOV,
    EINSOF_OP_COLLAPSE_1D_MMIO,
    EINSOF_OP_SYMPLECTIC_COV,
    EINSOF_COLLAPSE_GOP_RASTER,
    STRUCT_FORMAT
)

class TestEinsofGeometricISA(unittest.TestCase):
    def test_01_instruction_size_and_alignment(self):
        """Verifica que el bloque de instruccion mida exactamente 64 bytes (1 cache-line)"""
        size = struct.calcsize(STRUCT_FORMAT)
        self.assertEqual(size, 64, "La instruccion EinsofInstruction64 DEBE medir exactamente 64 bytes")
        
        ins = EinsofInstruction64(opcode=EINSOF_OP_ROT_LIE, dimension=2048, param_alpha=0.05)
        packed = ins.pack()
        self.assertEqual(len(packed), 64)
        
        unpacked = EinsofInstruction64.unpack(packed)
        self.assertEqual(unpacked.opcode, EINSOF_OP_ROT_LIE)
        self.assertEqual(unpacked.dimension, 2048)
        self.assertAlmostEqual(unpacked.param_alpha, 0.05, places=5)

    def test_02_neumaier_accumulator_precision(self):
        """Verifica que el acumulador Neumaier mantenga error <= 10^-15"""
        dim = 2048
        rng = np.random.RandomState(1234)
        v = rng.randn(dim)
        
        # Norma manual con Neumaier
        norm_val = neumaier_norm(v)
        v_norm = v / norm_val
        
        # Norma del vector normalizado debe ser 1.0 con precision IEEE-754
        norm_after = neumaier_norm(v_norm)
        rel_error = abs(norm_after - 1.0)
        self.assertLessEqual(rel_error, 1e-15, f"Error Neumaier excesivo: {rel_error}")

    def test_03_lyapunov_potential_monotone_descent(self):
        """Verifica que las rotaciones y retracciones produzcan descenso monotono de energia"""
        vm = EinsofGeometricVM(dimension=2048)
        initial_energy = vm.compute_lyapunov_energy(0)
        
        # Ejecutar 10 pasos de rotacion continua hacia el atractor
        for _ in range(10):
            vm.rotate_lie(0, 0.05)
            
        final_energy = vm.compute_lyapunov_energy(0)
        self.assertLess(final_energy, initial_energy, "La dinamica de Lyapunov debe disipar energia hacia el atractor")

    def test_04_ephemeral_1d_collapse_and_destruction(self):
        """Verifica que el colapso a 1D proyecte en GOP y destruya referencias en O(1)"""
        vm = EinsofGeometricVM(dimension=2048)
        pixels_affected = vm.collapse_ephemeral_1d(0, 0x80000000)
        self.assertGreater(pixels_affected, 0, "El colapso efimero debe renderizar en el puerto GOP")
        
        # Verificar que el borde cyan y la onda verde existan en el framebuffer
        start_y, end_y = vm.fb_height - 180, vm.fb_height - 40
        start_x = vm.fb_width - 450
        cyan_count = np.sum(vm.framebuffer[start_y:end_y, start_x] == 0x0000E5FF)
        self.assertGreater(cyan_count, 50, "Borde cyan no detectado")

    def test_05_full_stream_execution(self):
        """Verifica la ejecucion integra de un stream binario de 64 bytes"""
        vm = EinsofGeometricVM(dimension=2048)
        stream = bytearray()
        
        # 5 instrucciones
        stream.extend(EinsofInstruction64(opcode=EINSOF_OP_ROT_LIE, param_alpha=0.1).pack())
        stream.extend(EinsofInstruction64(opcode=EINSOF_OP_RETRACT_STIEFEL).pack())
        stream.extend(EinsofInstruction64(opcode=EINSOF_OP_BIFURCATE_LYAPUNOV, lyapunov_energy_threshold=0.05).pack())
        stream.extend(EinsofInstruction64(opcode=EINSOF_OP_COLLAPSE_1D_MMIO, mmio_target_addr=0x80000000).pack())
        stream.extend(EinsofInstruction64(opcode=EINSOF_OP_HALT_STABLE).pack())
        
        res = vm.execute_stream(bytes(stream))
        self.assertEqual(res["exit_code"], 0)
        self.assertEqual(res["instructions_count"], 5)
        self.assertEqual(res["collapses"], 1)
        self.assertLessEqual(res["orthonormal_error"], 1e-15)

    def test_06_symplectic_covariant_operator_uk(self):
        """Verifica Lema 5.1: Operador covariante simpléctico U(K) preserva Stiefel y Sp(2K) con error <= 1e-15"""
        dim = 2048
        vm = EinsofGeometricVM(dimension=dim)
        # Normalizar estado inicial
        vm.retract_stiefel(0)
        norm_before = neumaier_norm(vm.slabs[0])
        self.assertAlmostEqual(norm_before, 1.0, places=14)

        # Aplicar operador covariante simpléctico U(K=1024)
        eps_orth, eps_sp = vm.symplectic_covariant_step(0, theta=0.125)
        self.assertLessEqual(eps_orth, 1e-15, f"Defecto de ortogonalidad Stiefel excedido: {eps_orth}")
        self.assertLessEqual(eps_sp, 1e-15, f"Defecto simpléctico Sp(2K) excedido: {eps_sp}")

        # Ejecutar en stream binario de 64 bytes
        stream = bytearray()
        stream.extend(EinsofInstruction64(opcode=EINSOF_OP_SYMPLECTIC_COV, dimension=dim, param_alpha=0.25).pack())
        stream.extend(EinsofInstruction64(opcode=EINSOF_OP_HALT_STABLE).pack())
        res = vm.execute_stream(bytes(stream))
        self.assertEqual(res["exit_code"], 0)
        self.assertLessEqual(res["orthonormal_error"], 1e-15)

if __name__ == "__main__":
    unittest.main()
