import subprocess
import os
import sys

vcvars = r"C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
cmd = f'call "{vcvars}" && cd /d E:\\EinsofOS\\src && cl /EHsc /std:c++20 /O2 /arch:AVX mathesis_vm.cpp /Fe:mathesis_vm.exe && mathesis_vm.exe'

print("[*] Ejecutando compilacion y corrida en silicio nativo de MATHESIS...")
res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
print(f"EXIT CODE: {res.returncode}")
sys.exit(res.returncode)
