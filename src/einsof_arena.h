#pragma once
#include <cstdint>
#include <cstddef>
#include <iostream>
#include <vector>
#include <cstring>

#if defined(_WIN32)
#include <windows.h>
#else
#include <sys/mman.h>
#include <unistd.h>
#endif

// Constantes maestras
constexpr uint64_t EINSOF_MAGIC = 0x45494E534F463031ULL; // "EINSOF01"
constexpr size_t CACHE_LINE_SIZE = 64;

#pragma pack(push, 1)
// Fat Pointer de 16 Bytes (Cabe en RDX:RAX)
struct EinsofFatPtr {
    uint64_t offset;    // Offset relativo al registro base R15
    uint64_t meta;      // [dim_d:32 | flags:8 | generation:8 | type_id:16]

    inline uint16_t get_type_id() const { return static_cast<uint16_t>(meta & 0xFFFF); }
    inline uint8_t  get_generation() const { return static_cast<uint8_t>((meta >> 16) & 0xFF); }
    inline uint8_t  get_flags() const { return static_cast<uint8_t>((meta >> 24) & 0xFF); }
    inline uint32_t get_dim_d() const { return static_cast<uint32_t>((meta >> 32) & 0xFFFFFFFF); }

    static inline uint64_t pack_meta(uint16_t type_id, uint8_t gen, uint8_t flags, uint32_t dim_d) {
        return (static_cast<uint64_t>(dim_d) << 32) |
               (static_cast<uint64_t>(flags) << 24) |
               (static_cast<uint64_t>(gen) << 16) |
               (static_cast<uint64_t>(type_id));
    }
};

// Cabecera física de 64 bytes que precede al tensor en memoria
struct EinsofSlabHeader {
    uint64_t magic;         // 0x00: "EINSOF01"
    uint16_t type_id;       // 0x08
    uint8_t  generation;    // 0x0A
    uint8_t  flags;         // 0x0B
    uint32_t dim_d;         // 0x0C
    uint64_t alloc_bitmap;  // 0x10: Bitmap de ocupacion interna
    double   neumaier_norm; // 0x18: Norma ortonormal calculada
    uint64_t crypto_hmac;   // 0x20: Firma de integridad
    uint8_t  padding[24];   // 0x28: Relleno para alinear exactamente a 64 bytes
};
#pragma pack(pop)

static_assert(sizeof(EinsofFatPtr) == 16, "EinsofFatPtr DEBE ser de exactamente 16 bytes");
static_assert(sizeof(EinsofSlabHeader) == 64, "EinsofSlabHeader DEBE ser de exactamente 64 bytes (1 cache line)");

// Gestor de Arena de Memoria Fisica Einsof (Fase 1: Bloque Unico / Base R15)
class EinsofMemoryArena {
private:
    uint8_t* base_memory_ptr;
    size_t   total_capacity_bytes;
    size_t   current_bump_offset;
    uint8_t  current_generation;

public:
    EinsofMemoryArena(size_t capacity_bytes = 256 * 1024 * 1024) // 256 MB por defecto
        : total_capacity_bytes(capacity_bytes), current_bump_offset(0), current_generation(1) {
#if defined(_WIN32)
        base_memory_ptr = static_cast<uint8_t*>(VirtualAlloc(
            nullptr, total_capacity_bytes, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
#else
        base_memory_ptr = static_cast<uint8_t*>(mmap(
            nullptr, total_capacity_bytes, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));
#endif
        if (!base_memory_ptr) {
            std::cerr << "[-] Error critico: No se pudo asignar la Arena base de memoria Einsof\n";
        }
    }

    ~EinsofMemoryArena() {
        if (base_memory_ptr) {
#if defined(_WIN32)
            VirtualFree(base_memory_ptr, 0, MEM_RELEASE);
#else
            munmap(base_memory_ptr, total_capacity_bytes);
#endif
        }
    }

    uint8_t* get_base_ptr() const { return base_memory_ptr; }

    // Asignar un Slab alineado a 64 bytes y retornar su FatPtr de 16 bytes
    EinsofFatPtr allocate_slab(uint16_t type_id, uint32_t dim_d, uint8_t flags) {
        size_t payload_bytes = dim_d * sizeof(double);
        size_t total_slab_bytes = sizeof(EinsofSlabHeader) + payload_bytes;

        // Alinear a 64 bytes
        size_t aligned_slab_bytes = (total_slab_bytes + 63) & ~63;

        if (current_bump_offset + aligned_slab_bytes > total_capacity_bytes) {
            std::cerr << "[-] Error: Memoria Arena agotada\n";
            return {0, 0};
        }

        uint64_t slab_offset = current_bump_offset;
        current_bump_offset += aligned_slab_bytes;

        // Configurar la cabecera en [base + slab_offset]
        EinsofSlabHeader* header = reinterpret_cast<EinsofSlabHeader*>(base_memory_ptr + slab_offset);
        header->magic = EINSOF_MAGIC;
        header->type_id = type_id;
        header->generation = current_generation;
        header->flags = flags;
        header->dim_d = dim_d;
        header->alloc_bitmap = 1;
        header->neumaier_norm = 1.0;
        header->crypto_hmac = 0;
        std::memset(header->padding, 0, sizeof(header->padding));

        // El payload arranca inmediatamente despues de los 64 bytes de cabecera
        uint64_t payload_offset = slab_offset + sizeof(EinsofSlabHeader);

        EinsofFatPtr ptr;
        ptr.offset = payload_offset;
        ptr.meta = EinsofFatPtr::pack_meta(type_id, current_generation, flags, dim_d);
        return ptr;
    }

    // Resolver un FatPtr a un puntero de memoria real (R15 + offset)
    double* resolve_payload(const EinsofFatPtr& ptr) {
        if (ptr.offset == 0) return nullptr;
        // Recuperar cabecera restando 64 bytes (O(1))
        EinsofSlabHeader* header = reinterpret_cast<EinsofSlabHeader*>(base_memory_ptr + ptr.offset - sizeof(EinsofSlabHeader));
        if (header->magic != EINSOF_MAGIC) {
            std::cerr << "[-] Alerta de seguridad: Magia de Slab corrupta o violada\n";
            return nullptr;
        }
        if (header->generation != ptr.get_generation()) {
            std::cerr << "[-] Alerta de seguridad: Use-After-Free detectado (Generacion obsoleta)\n";
            return nullptr;
        }
        return reinterpret_cast<double*>(base_memory_ptr + ptr.offset);
    }
};
