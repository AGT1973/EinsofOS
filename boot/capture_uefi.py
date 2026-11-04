#!/usr/bin/env python3
"""
capture_uefi.py — Captura un screenshot exacto del framebuffer UEFI GOP de EinsofOS corriendo bajo QEMU
"""
import os
import subprocess
import time
import socket

SOCK_PATH = "/tmp/qemu_mon.sock"
PPM_PATH = "/root/einsof_baremetal/boot/uefi_screen.ppm"
BMP_PATH = "/root/einsof_baremetal/boot/uefi_screen.bmp"

if os.path.exists(SOCK_PATH):
    os.remove(SOCK_PATH)
if os.path.exists(PPM_PATH):
    os.remove(PPM_PATH)

cmd = [
    "qemu-system-x86_64",
    "-enable-kvm", "-cpu", "host",
    "-smp", "4",
    "-drive", "if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd",
    "-drive", "format=raw,file=/root/einsof_baremetal/boot/einsof_os.img",
    "-m", "1024",
    "-monitor", f"unix:{SOCK_PATH},server,nowait",
    "-display", "none"
]

print("[*] Iniciando QEMU con hardware KVM y SMP 4 Cores...")
p = subprocess.Popen(cmd)

# Esperar a que UEFI bootee, despierte los nucleos y ejecute los comandos del shell (~5.0 segundos)
time.sleep(5.2)

print("[*] Conectando a QEMU Monitor para screendump...")
try:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(SOCK_PATH)
    time.sleep(0.2)
    s.sendall(f"screendump {PPM_PATH}\n".encode())
    time.sleep(0.5)
    s.sendall(b"quit\n")
    s.close()
except Exception as e:
    print(f"[-] Error comunicando con QEMU monitor: {e}")

try:
    p.wait(timeout=5)
except Exception:
    p.kill()

if os.path.exists(PPM_PATH):
    size = os.path.getsize(PPM_PATH)
    print(f"[+] Screendump capturado exitosamente: {PPM_PATH} ({size} bytes)")
    
    # Convertir PPM P6 a BMP de 32-bit o 24-bit
    with open(PPM_PATH, "rb") as f:
        header = f.readline().decode().strip()
        dims = f.readline().decode().strip()
        while dims.startswith("#"):
            dims = f.readline().decode().strip()
        w, h = map(int, dims.split())
        max_val = f.readline().decode().strip()
        raw_rgb = f.read()
    
    print(f"[+] Dimensiones de pantalla bare-metal detectadas: {w} x {h}")
    
    # Generar encabezado BMP (24-bit BGR)
    row_stride = ((w * 3 + 3) // 4) * 4
    image_size = row_stride * h
    file_size = 54 + image_size
    
    bmp_header = bytearray(54)
    bmp_header[0:2] = b'BM'
    bmp_header[2:6] = file_size.to_bytes(4, 'little')
    bmp_header[10:14] = (54).to_bytes(4, 'little')
    bmp_header[14:18] = (40).to_bytes(4, 'little')
    bmp_header[18:22] = w.to_bytes(4, 'little')
    bmp_header[22:26] = h.to_bytes(4, 'little')
    bmp_header[26:28] = (1).to_bytes(2, 'little')
    bmp_header[28:30] = (24).to_bytes(2, 'little')
    bmp_header[34:38] = image_size.to_bytes(4, 'little')
    
    bmp_data = bytearray(image_size)
    for y in range(h):
        # BMP se almacena de abajo hacia arriba
        ppm_y = (h - 1 - y)
        ppm_row_offset = ppm_y * w * 3
        bmp_row_offset = y * row_stride
        for x in range(w):
            r = raw_rgb[ppm_row_offset + x * 3]
            g = raw_rgb[ppm_row_offset + x * 3 + 1]
            b = raw_rgb[ppm_row_offset + x * 3 + 2]
            bmp_data[bmp_row_offset + x * 3] = b
            bmp_data[bmp_row_offset + x * 3 + 1] = g
            bmp_data[bmp_row_offset + x * 3 + 2] = r
            
    with open(BMP_PATH, "wb") as f:
        f.write(bmp_header)
        f.write(bmp_data)
        
    print(f"[+] Screenshot convertido a BMP: {BMP_PATH} ({os.path.getsize(BMP_PATH)} bytes)")
else:
    print("[-] No se encontro el archivo PPM.")
