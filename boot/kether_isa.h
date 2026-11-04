/**
 * ===============================================================================
 * KETHER GEOMETRIC ISA — C-ABI HEADER (SOVEREIGN SILICON INSTRUCTION SET)
 * Lenguaje de Programacion Polidimensional KETHER (EINSOF-L)
 * Autor: Ariel Garcia Traba (53 anos) | Gandalf
 * ===============================================================================
 */

#ifndef KETHER_ISA_H
#define KETHER_ISA_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Descubrimiento paramétrico de línea de caché (64B o 128B) */
#ifndef KETHER_CACHE_LINE_SIZE
#define KETHER_CACHE_LINE_SIZE 64
#endif

/* -------------------------------------------------------------------------------
 * OPCODES GEOMÉTRICOS DE KETHER (ISA 1.0)
 * ------------------------------------------------------------------------------- */
#define KETHER_OP_HALT_EQUILIBRIUM   0x00  /* Convergencia en cuenca de atraccion */
#define KETHER_OP_ROT_LIE_SO         0x01  /* Rotacion geodesica infinitesimal SO(D) */
#define KETHER_OP_RETRACT_STIEFEL    0x02  /* Retraccion polar ortonormal con Neumaier */
#define KETHER_OP_PROJECT_GRASSMANN  0x03  /* Proyeccion isometrica a subespacio */
#define KETHER_OP_ATTRACT_LYAPUNOV   0x04  /* Descenso por gradiente de potencial Phi(X) */
#define KETHER_OP_COLLAPSE_MMIO      0x05  /* Colapso efimero a 16.6ms en Framebuffer */
#define KETHER_OP_TELEPATHY_PMTP     0x06  /* DMA directo hacia nodo de silicio ALADIN */

/* -------------------------------------------------------------------------------
 * ESTRUCTURA DE LA TUPLA GEOMÉTRICA DE KETHER (EMPACADA A CACHE-LINE)
 * ------------------------------------------------------------------------------- */
#pragma pack(push, 1)

typedef struct {
    /* Encabezado de Despacho (8 Bytes) */
    uint8_t   opcode;            /* Codigo de operacion geometrica */
    uint8_t   flags;             /* Flags: 0x01=Strict_Isometry, 0x02=Trace */
    uint16_t  dimension;         /* Dimension D del manifold (ej: 2048) */
    uint32_t  lyapunov_epoch;    /* Contador de ciclo en el atractor */

    /* Descriptores de Silicio (16 Bytes) */
    uint32_t  source_slab_a;     /* Puntero a slab en RAM / SHM / Arena R15 */
    uint32_t  source_slab_b;     /* Puntero secundario para producto */
    uint32_t  dest_slab;         /* Puntero de asentamiento */
    float     energy_epsilon;    /* Tolerancia de convergencia de energia */

    /* Parametros Continuos de la Variedad (24 Bytes) */
    double    lie_theta;         /* Angulo infinitesimal dTheta */
    double    potential_alpha;   /* Coeficiente del pozo de potencial */
    double    damping_factor;    /* Amortiguamiento para estabilidad de Lyapunov */

    /* Verificacion de Silicio (16 Bytes - Total Base: 64 Bytes) */
    uint64_t  neumaier_checksum; /* Firma de norma IEEE-754 */
    uint32_t  dispatch_core;     /* Core asignado (Core 1 Tensorial) */
    uint32_t  reserved_align;    /* Relleno para alineacion exacta */

#if KETHER_CACHE_LINE_SIZE == 128
    /* Relleno de expansion para arquitecturas ARMv9 / Apple Silicon (128 Bytes) */
    uint8_t   extended_manifold_data[64];
#endif

} KetherTuple;

#pragma pack(pop)

/* Verificacion estricta en tiempo de compilacion del tamano de la tupla */
#if KETHER_CACHE_LINE_SIZE == 64
_Static_assert(sizeof(KetherTuple) == 64, "KetherTuple must be strictly 64 bytes aligned");
#elif KETHER_CACHE_LINE_SIZE == 128
_Static_assert(sizeof(KetherTuple) == 128, "KetherTuple must be strictly 128 bytes aligned");
#endif

#ifdef __cplusplus
}
#endif

#endif /* KETHER_ISA_H */
