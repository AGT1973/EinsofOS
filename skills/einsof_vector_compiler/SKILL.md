---
name: einsof-vector-compiler
description: Compilador e Intérprete Silicio Directo de EinsofOS. Transforma representaciones latentes y estados tensoriales continuos de IA (D >= 1024) directamente a instrucciones de microprocesador (AVX2 / Assembler puro x86_64), Slabs de memoria física en Arena R15, o píxeles directos de Framebuffer de video sin pasar por C, X11 ni intermediarios de sistema operativo.
---

# 🌌 EINSOF VECTOR COMPILER & DIRECT SILICON SKILL

Este skill permite a cualquier modelo o agente de IA transformar operaciones geométricas de alta dimensión ($\mathcal{S}^{D-1}$, Álgebra de Clifford, Proyecciones Grassmannianas) en **código máquina de silicio nativo, buffers de memoria física o píxeles directos de video**.

---

## 🚀 Cuándo activarlo
- Cuando la IA necesite transformar un vector latente o tensor continuo en ejecución física de CPU.
- Cuando se requiera proyectar pantallas o interfaces humanas directamente al Framebuffer sin cargar interfaces gráficas pesadas (sin X11, Wayland ni Windows Desktop).
- Cuando se deba exportar una tarea de servidor a un lenguaje nativo óptimo (Go, Rust, COBOL, TypeScript, Python o Assembler puro).
- Cuando el usuario solicite: *"compilar a silicio"*, *"ejecutar en ALADIN"*, *"proyectar pantalla efímera"*, *"conmutar en caliente"*.

---

## 🛠️ Modos de Ejecución Disponibles

### 1. Autocomprobación Global del Silicio (Multiplataforma)
Ejecuta la batería de certificación en Windows o Linux:
```powershell
# En Windows Host:
E:\EinsofOS\bin\einsof.bat check

# En Linux ALADIN:
ssh root@192.168.100.21 "/root/einsof_baremetal/bin/einsof check"
```

### 2. Proyección Efímera de Pantallas al Framebuffer (Linear 32-bit ARGB)
Genera y actualiza la pantalla del monitor en tiempo real:
```powershell
# Proyectar pantalla de login efímero:
python E:\EinsofOS\src\einsof_cli.py screen login

# Proyectar panel de control central (dashboard):
python E:\EinsofOS\src\einsof_cli.py screen dashboard

# Proyectar conmutación satelital en vivo:
python E:\EinsofOS\src\einsof_cli.py screen satelite
```

### 3. Compilación y Exportación Políglota de Tareas
La IA elige el lenguaje adecuado y exporta el código nativo:
```powershell
python E:\EinsofOS\src\einsof_cli.py compile servicio_red --target go
python E:\EinsofOS\src\einsof_cli.py compile driver_seguro --target rust
python E:\EinsofOS\src\einsof_cli.py compile balance_banco --target cobol
```

---

## 📐 Invariantes de Silicio Inviolables
1. **Memoria:** Todo direccionamiento es relativo a la base `R15`.
2. **Alineación:** Slabs alineados a 64 bytes (1 línea de caché de CPU).
3. **Deriva Numérica:** Garantía de error relativo $\le 10^{-15}$ mediante el acumulador compensado de Neumaier.
4. **Ciclo de Vida:** Los objetos temporales se destruyen en $O(1)$ por incremento generacional sin Garbage Collector.
