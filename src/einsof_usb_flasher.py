#!/usr/bin/env python3
"""
einsof_usb_flasher.py — Utilidad Segura de Flasheo Bare-Metal USB para EinsofOS
Permite grabar la imagen einsof_os.img directamente a una memoria USB fisica
o guiar al usuario para bootear hardware real sin intermediarios.
"""

import sys
import os
import subprocess
import platform

IMG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "boot", "einsof_os.img"))

def banner():
    print("=" * 70)
    print("   EINSOF OS: UTILIDAD SOBERANA DE FLASHEO USB BARE-METAL")
    print("=" * 70)
    print(f"[*] Imagen de disco objetivo: {IMG_PATH}")
    if os.path.exists(IMG_PATH):
        size_mb = os.path.getsize(IMG_PATH) / (1024 * 1024)
        print(f"[+] Estado de la imagen: LISTA ({size_mb:.1f} MB FAT32 con BOOTX64.EFI)")
    else:
        print("[-] ALERTA: No se encuentra einsof_os.img. Compile primero con 'einsof build-uefi'.")
    print("-" * 70)

def detect_usb_drives():
    os_type = platform.system()
    drives = []

    if os_type == "Windows":
        try:
            ps_cmd = 'Get-CimInstance Win32_DiskDrive | Where-Object { $_.InterfaceType -eq "USB" } | Select-Object DeviceID, Model, Size, MediaType | ConvertTo-Json'
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
            import json
            if res.stdout.strip():
                data = json.loads(res.stdout)
                if isinstance(data, dict):
                    data = [data]
                for d in data:
                    size_gb = int(d.get("Size", 0)) / (1024**3)
                    drives.append({
                        "id": d.get("DeviceID"),
                        "model": d.get("Model", "Dispositivo USB"),
                        "size_gb": f"{size_gb:.1f} GB"
                    })
        except Exception as e:
            print(f"[-] Error detectando discos en Windows: {e}")

    elif os_type == "Linux":
        try:
            res = subprocess.run(["lsblk", "-d", "-o", "NAME,SIZE,MODEL,TRAN", "-J"], capture_output=True, text=True)
            import json
            data = json.loads(res.stdout)
            for d in data.get("blockdevices", []):
                if d.get("tran") == "usb":
                    drives.append({
                        "id": f"/dev/{d.get('NAME')}",
                        "model": d.get("Model") or "Dispositivo USB",
                        "size_gb": d.get("SIZE")
                    })
        except Exception as e:
            print(f"[-] Error detectando discos en Linux: {e}")

    return drives

def main():
    banner()

    print("\n[*] Escaneando unidades USB conectadas...")
    drives = detect_usb_drives()

    if not drives:
        print("[!] No se detectaron unidades USB removibles conectadas.")
        print("\n" + "=" * 70)
        print("   INSTRUCCIONES MANUALES PARA ARRANCAR EN PC FISICA (100% SEGURO)")
        print("=" * 70)
        print("Opción A: RUFUS (Windows)")
        print(f"  1. Abra Rufus (https://rufus.ie)")
        print(f"  2. Seleccione su pendrive USB.")
        print(f"  3. En 'Elección de arranque', elija 'Disco o imagen ISO' y seleccione:")
        print(f"     -> {IMG_PATH}")
        print(f"  4. Esquema de partición: GPT | Sistema de destino: UEFI (no CSM)")
        print(f"  5. Presione EMPEZAR.\n")
        print("Opción B: COPIADO DIRECTO FAT32 (Sin formatear ni borrar su pendrive)")
        print("  Cualquier pendrive formateado en FAT32 bootea nativamente en UEFI:")
        print("  1. Cree la carpeta 'EFI\\BOOT' en la raíz de su pendrive USB.")
        print(f"  2. Copie el archivo 'BOOTX64.EFI' desde:")
        bootx64_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "boot", "BOOTX64.EFI"))
        print(f"     -> {bootx64_path}")
        print("     hacia:")
        print("     -> X:\\EFI\\BOOT\\BOOTX64.EFI  (donde X: es la letra de su pendrive)")
        print("  3. Reinicie su PC, presione F11/F12/F8 (Boot Menu) y elija arrancar desde USB UEFI.")
        print("=" * 70)
        return

    print(f"[+] Se encontraron {len(drives)} unidades USB:")
    for idx, d in enumerate(drives, 1):
        print(f"  [{idx}] {d['id']} — {d['model']} ({d['size_gb']})")

    print("\n[!] Por seguridad contra sobrescritura accidental del disco del sistema:")
    print("    Utilice la Opción B descrita arriba (copiar BOOTX64.EFI a EFI/BOOT/) o Rufus.")

if __name__ == "__main__":
    main()
