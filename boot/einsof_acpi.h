/* einsof_acpi.h — Descubrimiento de Hardware y Nucleos Multi-Core via ACPI MADT en Bare-Metal */
#ifndef EINSOF_ACPI_H
#define EINSOF_ACPI_H

#include <efi.h>
#include <efilib.h>

#define ACPI_MAX_CORES 32

typedef struct {
    UINT8  apic_id;
    UINT8  acpi_processor_id;
    UINT32 flags;
    BOOLEAN enabled;
} CoreDescriptor;

typedef struct {
    UINT32 local_apic_base;
    UINT32 core_count;
    CoreDescriptor cores[ACPI_MAX_CORES];
    CHAR8 oem_id[7];
} AcpiTopology;

// Cabecera generica de tabla ACPI
#pragma pack(push, 1)
typedef struct {
    CHAR8  signature[4];
    UINT32 length;
    UINT8  revision;
    UINT8  checksum;
    CHAR8  oem_id[6];
    CHAR8  oem_table_id[8];
    UINT32 oem_revision;
    UINT32 creator_id;
    UINT32 creator_revision;
} AcpiDescriptionHeader;

typedef struct {
    CHAR8  signature[8]; // "RSD PTR "
    UINT8  checksum;
    CHAR8  oem_id[6];
    UINT8  revision;
    UINT32 rsdt_address;
    UINT32 length;
    UINT64 xsdt_address;
    UINT8  extended_checksum;
    UINT8  reserved[3];
} RsdpDescriptor20;

typedef struct {
    AcpiDescriptionHeader header;
    UINT32 local_apic_address;
    UINT32 flags;
} MadtHeader;

typedef struct {
    UINT8 type;
    UINT8 length;
} MadtSubtableHeader;

typedef struct {
    MadtSubtableHeader header;
    UINT8 acpi_processor_id;
    UINT8 apic_id;
    UINT32 flags; // bit 0 = Enabled
} MadtProcessorLocalApic;
#pragma pack(pop)

static inline BOOLEAN compare_sig(const CHAR8 *a, const CHAR8 *b, UINTN len) {
    for (UINTN i = 0; i < len; ++i) {
        if (a[i] != b[i]) return FALSE;
    }
    return TRUE;
}

static inline void parse_madt(MadtHeader *madt, AcpiTopology *topo) {
    if (!madt || !topo) return;

    topo->local_apic_base = madt->local_apic_address;
    topo->core_count = 0;

    for (int i = 0; i < 6; ++i) {
        topo->oem_id[i] = madt->header.oem_id[i];
    }
    topo->oem_id[6] = '\0';

    UINT8 *ptr = (UINT8*)madt + sizeof(MadtHeader);
    UINT8 *end = (UINT8*)madt + madt->header.length;

    while (ptr < end) {
        MadtSubtableHeader *sub = (MadtSubtableHeader*)ptr;
        if (sub->length < sizeof(MadtSubtableHeader) || (ptr + sub->length) > end) break;

        if (sub->type == 0) { // Processor Local APIC
            MadtProcessorLocalApic *lapic = (MadtProcessorLocalApic*)ptr;
            if (topo->core_count < ACPI_MAX_CORES) {
                CoreDescriptor *core = &topo->cores[topo->core_count];
                core->apic_id = lapic->apic_id;
                core->acpi_processor_id = lapic->acpi_processor_id;
                core->flags = lapic->flags;
                core->enabled = (lapic->flags & 1) != 0;
                topo->core_count++;
            }
        }
        ptr += sub->length;
    }
}

static inline BOOLEAN find_acpi_topology(EFI_SYSTEM_TABLE *SystemTable, AcpiTopology *topo) {
    if (!SystemTable || !topo) return FALSE;

    topo->core_count = 0;
    topo->local_apic_base = 0xFEE00000; // Default Local APIC Base

    EFI_GUID acpi20TableGuid = ACPI_20_TABLE_GUID;
    EFI_GUID acpi10TableGuid = ACPI_TABLE_GUID;
    VOID *rsdp_ptr = NULL;

    for (UINTN i = 0; i < SystemTable->NumberOfTableEntries; ++i) {
        EFI_CONFIGURATION_TABLE *entry = &SystemTable->ConfigurationTable[i];
        if (CompareGuid(&entry->VendorGuid, &acpi20TableGuid) == 0) {
            rsdp_ptr = entry->VendorTable;
            break;
        }
        if (CompareGuid(&entry->VendorGuid, &acpi10TableGuid) == 0) {
            rsdp_ptr = entry->VendorTable;
        }
    }

    if (!rsdp_ptr) return FALSE;

    RsdpDescriptor20 *rsdp = (RsdpDescriptor20*)rsdp_ptr;
    if (!compare_sig(rsdp->signature, "RSD PTR ", 8)) return FALSE;

    // Buscar MADT via XSDT (64-bit) o RSDT (32-bit)
    if (rsdp->revision >= 2 && rsdp->xsdt_address != 0) {
        AcpiDescriptionHeader *xsdt = (AcpiDescriptionHeader*)(UINTN)rsdp->xsdt_address;
        if (compare_sig(xsdt->signature, "XSDT", 4)) {
            UINT32 entries = (xsdt->length - sizeof(AcpiDescriptionHeader)) / sizeof(UINT64);
            UINT64 *tables = (UINT64*)((UINT8*)xsdt + sizeof(AcpiDescriptionHeader));
            for (UINT32 i = 0; i < entries; ++i) {
                AcpiDescriptionHeader *table = (AcpiDescriptionHeader*)(UINTN)tables[i];
                if (compare_sig(table->signature, "APIC", 4)) {
                    parse_madt((MadtHeader*)table, topo);
                    return TRUE;
                }
            }
        }
    }

    // Fallback RSDT (32-bit)
    if (rsdp->rsdt_address != 0) {
        AcpiDescriptionHeader *rsdt = (AcpiDescriptionHeader*)(UINTN)rsdp->rsdt_address;
        if (compare_sig(rsdt->signature, "RSDT", 4)) {
            UINT32 entries = (rsdt->length - sizeof(AcpiDescriptionHeader)) / sizeof(UINT32);
            UINT32 *tables = (UINT32*)((UINT8*)rsdt + sizeof(AcpiDescriptionHeader));
            for (UINT32 i = 0; i < entries; ++i) {
                AcpiDescriptionHeader *table = (AcpiDescriptionHeader*)(UINTN)tables[i];
                if (compare_sig(table->signature, "APIC", 4)) {
                    parse_madt((MadtHeader*)table, topo);
                    return TRUE;
                }
            }
        }
    }

    return (topo->core_count > 0);
}

#endif /* EINSOF_ACPI_H */
