"""
PMTP Model & Hardware Dynamic Inspector (pmtp_inspector.py)
Interroga tanto al hardware subyacente (CPU/AVX, GPU, TPU, QPU)
como al modelo/tensor de entrada (variedad de Stiefel, dimensiones,
defecto asintótico, tier de precisión alcanzado).
"""
import os, sys, platform, json
import numpy as np

PRECISION_TIERS = [
    (1e-50, "TIER_ARBITRARY_50",    "Precision Arbitraria (mpmath / FP256)"),
    (1e-35, "TIER_QUAD_35",         "Quad Precision IEEE 754-2008 (binary128)"),
    (1e-25, "TIER_EXTENDED_25",     "Precision Extendida x87 / AVX Neumaier"),
    (3e-17, "TIER_SUB_EPSILON_17",   "Sub-Épsilon FP64 (Simetría Perfecta)"),
    (3e-16, "TIER_MACHINE_EPS_16",   "Límite Atómico IEEE 754 (binary64)"),
    (1e-15, "TIER_STIEFEL_FLOOR_15", "Piso Clásico de Retracción Numérica"),
    (1e-14, "TIER_ACCUMULATION_14",  "Margen Asintótico para D >= 8192"),
    (1e-8,  "TIER_LEGACY_FP32_8",   "Aproximación Polinomial Taylor/FP32 (OBSOLETA)")
]

def interrogate_hardware() -> dict:
    """Interroga capacidades de cómputo físico (CPU, SIMD, GPU, QPU)."""
    hw_info = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "arch": platform.machine(),
        "cpu_count": os.cpu_count(),
        "simd_avx2": False,
        "gpu_available": False,
        "gpu_name": None,
        "qpu_bridge": False
    }
    
    # Check AVX2
    try:
        if sys.platform == "win32":
            import ctypes
            # IsProcessorFeaturePresent(PF_AVX2_INSTRUCTIONS_AVAILABLE = 40)
            hw_info["simd_avx2"] = bool(ctypes.windll.kernel32.IsProcessorFeaturePresent(40))
        elif sys.platform.startswith("linux"):
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo", "r") as f:
                    content = f.read()
                    hw_info["simd_avx2"] = "avx2" in content
    except Exception:
        pass
        
    # Check GPU (PyTorch/CUDA if present)
    try:
        import torch
        if torch.cuda.is_available():
            hw_info["gpu_available"] = True
            hw_info["gpu_name"] = torch.cuda.get_device_name(0)
            hw_info["gpu_vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
    except Exception:
        pass

    # Check QPU Bridge via active_vault or env
    try:
        import psycopg2
        conn = psycopg2.connect(dbname='polydim_active_db', user='postgres', password='postgres', host='localhost')
        cur = conn.cursor()
        cur.execute("SELECT key_name FROM active_vault WHERE key_name ILIKE '%ibm_quantum%' OR key_name ILIKE '%qpu%';")
        if cur.fetchone():
            hw_info["qpu_bridge"] = True
        conn.close()
    except Exception:
        pass

    return hw_info

def interrogate_model_tensor(matrix_or_path, model_name: str = "Unknown") -> dict:
    """
    Interroga al modelo o tensor:
    - Dimensiones y variedad St(k, d)
    - Precisión de almacenamiento original (dtype)
    - Defecto de Stiefel medido en float64
    - Clasificación en el Escalafón de Precisión (Tier)
    - Dictamen de compatibilidad Ghost Protocol / PMTP
    """
    if isinstance(matrix_or_path, str):
        # Load from safetensors or npy
        if matrix_or_path.endswith('.safetensors'):
            from safetensors.numpy import load_file
            data = load_file(matrix_or_path)
            key = next((k for k in ["stiefel_matrix", "weight", "pmtp_stiefel_matrix"] if k in data), list(data.keys())[0])
            mat = data[key]
        elif matrix_or_path.endswith('.npy'):
            mat = np.load(matrix_or_path)
        else:
            raise ValueError(f"Formato no soportado: {matrix_or_path}")
    else:
        mat = np.asarray(matrix_or_path)

    orig_dtype = str(mat.dtype)
    shape = mat.shape
    if len(shape) != 2:
        raise ValueError(f"Se esperaba tensor 2D para variedad Stiefel, recibido shape={shape}")

    k, d = shape
    # Para St(k, d), k <= d: comprobamos ortogonalidad de filas: Q Q^T = I_k
    mat_f64 = np.asarray(mat, dtype=np.float64)
    if k <= d:
        err = mat_f64 @ mat_f64.T - np.eye(k, dtype=np.float64)
        defect = float(np.linalg.norm(err, 'fro') / k)
    else:
        err = mat_f64.T @ mat_f64 - np.eye(d, dtype=np.float64)
        defect = float(np.linalg.norm(err, 'fro') / d)

    # Identificar Tier alcanzado sin conformismo
    certified_tier = "TIER_DEGRADED"
    tier_desc = "Fallo de Invariante de Stiefel"
    for threshold, name, desc in PRECISION_TIERS:
        if defect <= threshold:
            certified_tier = name
            tier_desc = desc
            break

    return {
        "model_name": model_name,
        "stiefel_manifold": f"St({k}, {d})",
        "k_dim": k,
        "d_dim": d,
        "input_dtype": orig_dtype,
        "stiefel_defect_fp64": defect,
        "certified_tier": certified_tier,
        "tier_description": tier_desc,
        "ghost_protocol_ready": defect <= 3e-16,
        "sovereign_status": "CERTIFIED_SOVEREIGN" if defect <= 3e-16 else ("ACCEPTABLE_LEGACY" if defect <= 1e-14 else "REJECTED")
    }

def pmtp_interrogate_full(matrix_or_path, model_name: str = "Unknown") -> dict:
    """Interrogación completa simétrica: Hardware + Modelo."""
    return {
        "hardware": interrogate_hardware(),
        "model": interrogate_model_tensor(matrix_or_path, model_name)
    }

if __name__ == "__main__":
    print("=== INTERROGACIÓN SIMÉTRICA PMTP-CORE ===")
    hw = interrogate_hardware()
    print("1. Hardware Detectado:")
    for k, v in hw.items():
        print(f"   - {k}: {v}")

    # Probar con matriz generada St(2048, 4096)
    print("\n2. Interrogando Modelo Sintético SVD:")
    rng = np.random.default_rng(42)
    M = rng.standard_normal((1024, 2048), dtype=np.float64)
    U, _, Vt = np.linalg.svd(M, full_matrices=False)
    Q = U @ Vt
    
    report = interrogate_model_tensor(Q, "Synthetic-Qwen3-SVD")
    for k, v in report.items():
        print(f"   - {k}: {v}")
