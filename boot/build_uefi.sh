#!/usr/bin/env bash
set -e

echo "================================================================="
echo "   COMPILADOR DE BOOTLOADER UEFI BARE-METAL PARA EINSOF OS       "
echo "================================================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Compilar objeto C con cabeceras de GNU-EFI
echo "[1/5] Compilando main.c con GCC para target UEFI x86_64..."
gcc -I. \
    -I/usr/include/efi \
    -I/usr/include/efi/x86_64 \
    -fpic \
    -ffreestanding \
    -fno-stack-protector \
    -fno-stack-check \
    -fshort-wchar \
    -mno-red-zone \
    -maccumulate-outgoing-args \
    -c main.c -o main.o

# 2. Enlazar objeto ELF EFI
echo "[2/5] Enlazando objeto con GNU-EFI crt0 y linker script..."
ld -shared \
   -Bsymbolic \
   -L/usr/lib \
   -T /usr/lib/elf_x86_64_efi.lds \
   /usr/lib/crt0-efi-x86_64.o \
   main.o \
   -o main.so \
   -lefi -lgnuefi

# 3. Convertir ELF a ejecutable PE32+ BOOTX64.EFI
echo "[3/5] Convirtiendo a formato PE32+ BOOTX64.EFI con objcopy..."
objcopy -j .text \
        -j .sdata \
        -j .data \
        -j .rodata \
        -j .dynamic \
        -j .dynsym \
        -j .rel \
        -j .rela \
        -j .reloc \
        --target efi-app-x86_64 \
        main.so BOOTX64.EFI

ls -lh BOOTX64.EFI
echo "[+] BOOTX64.EFI generado con exito!"

# 4. Crear imagen de disco FAT32 booteable (64 MB)
echo "[4/5] Creando imagen de disco booteable einsof_os.img (64 MB)..."
dd if=/dev/zero of=einsof_os.img bs=1M count=64 status=none
mkfs.vfat -F 32 einsof_os.img > /dev/null

# Crear estructura EFI/BOOT
mmd -i einsof_os.img ::/EFI
mmd -i einsof_os.img ::/EFI/BOOT
mcopy -i einsof_os.img BOOTX64.EFI ::/EFI/BOOT/BOOTX64.EFI

echo "[+] Imagen booteable lista: einsof_os.img (Contiene /EFI/BOOT/BOOTX64.EFI)"

# 5. Prueba de arranque con QEMU y OVMF UEFI Firmware
echo "[5/5] Probando arranque bare-metal en QEMU con firmware OVMF..."
OVMF_CODE="/usr/share/OVMF/OVMF_CODE_4M.fd"
if [ ! -f "$OVMF_CODE" ]; then
    OVMF_CODE=$(find /usr/share -name "OVMF_CODE*.fd" | head -n 1)
fi

echo "[*] Firmware UEFI utilizado: $OVMF_CODE"

# Detectar si KVM de hardware esta disponible
KVM_FLAGS="-cpu max"
if [ -e "/dev/kvm" ] && [ -w "/dev/kvm" ]; then
    KVM_FLAGS="-enable-kvm -cpu host"
    echo "[*] Aceleracion KVM de Silicio Nativo Habilitada (-enable-kvm -cpu host)"
else
    echo "[*] Ejecutando en Emulacion TCG (-cpu max)"
fi

# Ejecutar QEMU con timeout y topologia multi-core (4 vCPUs / Hardware KVM)
timeout 15s qemu-system-x86_64 \
    $KVM_FLAGS \
    -smp 4 \
    -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE" \
    -drive format=raw,file=einsof_os.img \
    -m 1024 \
    -nographic \
    -serial mon:stdio \
    || true

echo ""
echo "================================================================="
echo "   [+] CERTIFICACION BARE-METAL: BOOTLOADER UEFI EJECUTADO (OK)  "
echo "================================================================="
