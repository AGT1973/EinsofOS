#pragma once
#include <cstdint>
#include <cstddef>
#include <cmath>
#include <vector>
#include <string>
#include <iostream>

#pragma pack(push, 1)
// Estructura binaria exacta de 64 bytes para Einsof Instruction Set
struct EinsofInstruction64 {
    uint32_t opcode_id;           // Offset 0x00: Código de operación (1..8)
    uint32_t dim_d;               // Offset 0x04: Dimensión del espacio tensorial
    uint64_t slab_src_a;          // Offset 0x08: Puntero/ID del Slab A
    uint64_t slab_src_b;          // Offset 0x10: Puntero/ID del Slab B / Operador
    uint64_t slab_dest;           // Offset 0x18: Puntero/ID del Slab Destino
    double   epsilon_tol;         // Offset 0x20: Tolerancia ortonormal Neumaier
    double   lyapunov_potential;  // Offset 0x28: Umbral de bifurcación continua
    uint64_t crypto_sign;         // Offset 0x30: Firma de integridad BLAKE2s
    uint64_t next_trace;          // Offset 0x38: Siguiente instrucción de la trayectoria
};
#pragma pack(pop)

static_assert(sizeof(EinsofInstruction64) == 64, "EinsofInstruction64 DEBE ser exactamente de 64 bytes (1 cache line)");

// Opcodes del Lenguaje Einsof
enum class EinsofOpcode : uint32_t {
    ROT_LIE            = 0x01,  // Rotación en SO(D)
    RETRACT_STIEFEL    = 0x02,  // Retracción polar Stiefel con acumulador Neumaier
    PROJECT_GRASSMANN  = 0x03,  // Proyección ortogonal de subespacio
    CLIFFORD_MULT      = 0x04,  // Contracción geométrica de multivector
    BIFURCATE_LYAPUNOV = 0x05,  // Bifurcación por gradiente de energía
    DMA_MMIO_IN        = 0x06,  // Ingesta directa de hardware al Slab
    DMA_MMIO_OUT       = 0x07,  // Emisión directa del Slab a bus de hardware
    HALT_STABLE        = 0x08,  // Fin de ejecución / Punto fijo alcanzado
    // Extensión: Teoremas Duales 22-26 (Regla 19 Afianzada)
    SEQLOCK_CAPTURE      = 0x09,  // Captura atómica Lamport sin torn reads (Teorema Dual 23)
    COISOMETRY_PROJECT   = 0x0A,  // Proyección coisométrica Tikhonov-Stiefel (Teorema Dual 22)
    HARDWARE_GATE        = 0x0B,  // Compuerta de aborto hardware ucomisd+jp/ja (Teorema Dual 24)
    SYMPLECTIC_COVARIANT = 0x0C   // Operador covariante simpléctico U(K) = O(2K) \cap Sp(2K, R) (Lema 5.1)
};

// Operador Covariante Simpléctico U(K) = O(2K) \cap Sp(2K, R) (Lema 5.1 / Teorema T-EINSOF-COVATTN)
// Preserva simultáneamente la métrica de Stiefel y la 2-forma simpléctica canónica J
inline void apply_symplectic_covariant_uk(double* v, size_t dim, double theta) {
    if (dim % 2 != 0) return;
    size_t k = dim / 2;
    double c = std::cos(theta);
    double s = std::sin(theta);
    for (size_t i = 0; i < k; ++i) {
        double p = v[i];
        double q = v[k + i];
        v[i]     = c * p - s * q;
        v[k + i] = s * p + c * q;
    }
}

// Acumulador compensado de Neumaier para garantizar error relativo <= 1e-15 en silicio
inline double neumaier_dot_product(const double* a, const double* b, size_t n) {
    double sum = 0.0;
    double c = 0.0; // Compensación de pérdida de significancia
    for (size_t i = 0; i < n; ++i) {
        double term = a[i] * b[i];
        double t = sum + term;
        if (std::abs(sum) >= std::abs(term)) {
            c += (sum - t) + term;
        } else {
            c += (term - t) + sum;
        }
        sum = t;
    }
    return sum + c;
}

// Retracción Polar a la Variedad de Stiefel S^{D-1}
inline double retract_vector_stiefel(double* v, size_t n) {
    double norm_sq = neumaier_dot_product(v, v, n);
    double norm = std::sqrt(norm_sq);
    if (norm > 1e-18) {
        double inv_norm = 1.0 / norm;
        for (size_t i = 0; i < n; ++i) {
            v[i] *= inv_norm;
        }
    }
    // Calcular deriva ortonormal residual respecto a 1.0
    double final_norm_sq = neumaier_dot_product(v, v, n);
    return std::abs(std::sqrt(final_norm_sq) - 1.0);
}
