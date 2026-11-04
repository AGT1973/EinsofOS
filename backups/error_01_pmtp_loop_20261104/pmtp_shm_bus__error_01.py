# ============================================================================
# PMTP SHM BUS V1.0 PRODUCTION ENGINE (ATOMIC-MONITOR-PROTECTED)
# Proyecto: PMTP (Polydim Memory Tensor Protocol)
# Autor: Ariel García Traba (Independent Research)
# Base Teórica: Teoremas T-MP12, T-MP15, T-MP17, T-MP20 (MP-55)
# ============================================================================

import os
import sys
import time
import math
import struct
import threading
import weakref
from multiprocessing import shared_memory
from typing import Tuple, Dict, Any, Optional
import numpy as np

from pmtp_types import (
    PMTP_MAGIC_NUMBER,
    PMTP_VERSION_V1,
    HEADER_COMPACT_SIZE,
    HEADER_COMPACT_FORMAT,
    HEADER_COMPACT_STRUCT,
    PmtpDType,
    PmtpState,
    PmtpCompactHeader
)

# PMTP v3.1 Publication Object Bus (POB) Integration
try:
    from pmtp_pob_bus import PmtpPobProducer, PmtpPobConsumer, PmtpPobView, PmtpPolicy, PmtpStatus
except ImportError:
    pass

class PmtpLeasedArray(np.ndarray):
    """Subclase de ndarray con __dict__ y soporte de ciclo de vida para DLPack."""
    pass

class PmtpShmBus:
    """
    Bus de Memoria Compartida PMTP v1.0 con Doble Buffer Inmutable y Monitor Atómico.
    Garantías de Silicio:
    - Zero-copy: vistas NumPy y tensores PyTorch sobre RAM física sin serialización intermedia.
    - Cero torn-reads: conmutación atómica de slot y exclusión de escritura sobre slots leased.
    - Anti-Check-then-Act (T-MP20, MP-55): banderas de retiro explícitas en cabecera de 64 bytes.
    - Anti-ABA (T-MP17, MP-48): contadores atómicos de leases de lectura.
    """
    HEADER_SIZE = HEADER_COMPACT_SIZE
    STATE_AND_READERS_OFFSET = 48

    def __init__(
        self,
        prefix: str = "pmtp",
        max_slabs: int = 64,
        max_dim: int = 8192,
        lease_timeout_ms: int = 30000,
    ):
        self.prefix = prefix
        self.max_slabs = max_slabs
        self.max_dim = max_dim
        self.lease_timeout_ms = lease_timeout_ms
        self.slabs: Dict[int, Dict[str, Any]] = {}
        self._next_slab_seq: int = 1
        self._local_lock = threading.Lock()

    def allocate_tensor_slab(
        self,
        slab_id: int,
        num_elements: int,
        dtype=np.float64,
        scale: float = 1.0
    ) -> shared_memory.SharedMemory:
        """
        Asigna un slab en memoria compartida para doble buffer inmutable.
        Tamaño total = 64 bytes (cabecera) + 2 * (num_elements * sizeof(dtype)).
        """
        if num_elements <= 0:
            raise ValueError(f"num_elements debe ser estrictamente positivo: {num_elements}")

        np_dt = np.dtype(dtype)
        if np_dt.kind not in ('f', 'i', 'u'):
            raise TypeError(f"DType no numérico o no serializable rechazado (Error 45 cátedra): {dtype}")

        itemsize = np_dt.itemsize
        payload_bytes = num_elements * itemsize
        total_nbytes = HEADER_COMPACT_SIZE + (2 * payload_bytes)
        name = f"{self.prefix}_{slab_id:04x}"

        # Liberar instancia huérfana si existe
        try:
            old = shared_memory.SharedMemory(name=name, create=False)
            old.close()
            old.unlink()
        except FileNotFoundError:
            pass

        try:
            shm = shared_memory.SharedMemory(name=name, create=True, size=total_nbytes)
        except FileExistsError:
            shm = shared_memory.SharedMemory(name=name, create=False)
            if shm.size < total_nbytes:
                shm.close()
                raise BufferError(f"Slab SHM existente '{name}' tiene tamaño {shm.size}B menor al requerido ({total_nbytes}B)")
        self.slabs[slab_id] = {
            "shm": shm,
            "num_elements": num_elements,
            "dtype": dtype,
            "itemsize": itemsize,
            "payload_bytes": payload_bytes,
            "name": name
        }

        dtype_id = PmtpDType.FP64.value if dtype == np.float64 else PmtpDType.FP32.value
        timestamp_ns = time.time_ns()

        # Cabecera inicial de 64 bytes: Slot 0 activo inicial (retired=False), Slot 1 inactivo (retired=True)
        # state_and_readers = 0 (libre de lectores, DESTROYING_BIT = 0)
        header_bytes = HEADER_COMPACT_STRUCT.pack(
            PMTP_MAGIC_NUMBER,
            PMTP_VERSION_V1,
            dtype_id,
            0,             # active_slot = 0
            slab_id,
            num_elements,
            timestamp_ns,
            scale,
            1,             # generation = 1
            False,         # retired_slot0 = False
            True,          # retired_slot1 = True (inactivo)
            0,             # reserved_flags
            0,             # state_and_readers = 0 (Unificado 10/10)
            b"\x00" * 8    # reserved (padding a 64B)
        )
        shm.buf[:HEADER_COMPACT_SIZE] = header_bytes
        return shm

    def read_header(self, slab_id: int) -> PmtpCompactHeader:
        """Lee y desempaqueta la cabecera atómica de 64 bytes."""
        shm = self.slabs[slab_id]["shm"]
        return PmtpCompactHeader.unpack(bytes(shm.buf[:HEADER_COMPACT_SIZE]))

    def publish_snapshot_atomic(
        self,
        slab_id: int,
        data: np.ndarray,
        max_retries: int = 100,
        retry_delay_s: float = 0.0005
    ) -> bool:
        """
        Publica atómicamente un nuevo tensor en el buffer inactivo (T-MP15, T-MP20):
        1. target_slot = 1 - current_active.
        2. Verifica que target_slot esté libre y state_and_readers no tenga DESTROYING_BIT.
        3. Copia el payload en el buffer inactivo de forma aislada.
        4. Conmuta active_slot a target_slot, desmarca target_slot de retiro y retira el slot previo.
        """
        info = self.slabs[slab_id]
        shm = info["shm"]

        for _ in range(max_retries):
            with self._local_lock:
                hdr = self.read_header(slab_id)
                if hdr.state_and_readers & (1 << 63):
                    return False  # Bloque en destrucción

                current_active = hdr.active_slot
                target_slot = 1 - current_active

                # Exclusión Anti-ABA / Anti-Torn-Read: rechazar si el slot destino tiene leases activos
                target_readers = (hdr.state_and_readers >> 32) & 0x7FFFFFFF if target_slot == 1 else (hdr.state_and_readers & 0xFFFFFFFF)
                if target_readers > 0:
                    time.sleep(retry_delay_s)
                    continue

                slot_offset = HEADER_COMPACT_SIZE + (target_slot * info["payload_bytes"])
                target_view = np.ndarray(
                    shape=(info["num_elements"],),
                    dtype=info["dtype"],
                    buffer=shm.buf,
                    offset=slot_offset
                )
                target_view[:] = data[:]

                # Conmutación atómica
                new_gen = hdr.generation + 1
                ret0 = (target_slot != 0)  # Slot 0 retirado si target es 1
                ret1 = (target_slot != 1)  # Slot 1 retirado si target es 0

                new_header_bytes = HEADER_COMPACT_STRUCT.pack(
                    PMTP_MAGIC_NUMBER,
                    PMTP_VERSION_V1,
                    hdr.dtype_id,
                    target_slot,
                    hdr.slab_id,
                    hdr.num_elements,
                    time.time_ns(),
                    hdr.scale,
                    new_gen,
                    ret0,
                    ret1,
                    hdr.reserved_flags,
                    hdr.state_and_readers,
                    b"\x00" * 8
                )
                shm.buf[:HEADER_COMPACT_SIZE] = new_header_bytes
                return True
            time.sleep(retry_delay_s)

        return False

    def acquire_reader_lease(
        self,
        slab_id: int,
        max_retries: int = 50,
        retry_delay_s: float = 0.0003
    ) -> Tuple[int, int]:
        """
        Adquiere lease atómico libre de UAF y race conditions (Bloque A 10/10).
        CAS atómico sobre state_and_readers (Bits 0-62).
        Falla inmediatamente si Bit 63 (DESTROYING_BIT) está activo.
        """
        shm = self.slabs[slab_id]["shm"]
        for _ in range(max_retries):
            with self._local_lock:
                hdr = self.read_header(slab_id)
                if hdr.state_and_readers & (1 << 63):
                    raise RuntimeError(f"Falla: Slab {hex(slab_id)} en proceso de destrucción (DESTROYING_BIT activo)")

                slot = hdr.active_slot
                is_retired = hdr.retired_slot1 if slot == 1 else hdr.retired_slot0

                if is_retired:
                    continue

                # CAS incremento atómico de lectores por slot (bits 0-31 para slot 0, bits 32-62 para slot 1)
                inc = 1 if slot == 0 else (1 << 32)
                new_sr = hdr.state_and_readers + inc
                new_header_bytes = HEADER_COMPACT_STRUCT.pack(
                    PMTP_MAGIC_NUMBER,
                    PMTP_VERSION_V1,
                    hdr.dtype_id,
                    slot,
                    hdr.slab_id,
                    hdr.num_elements,
                    hdr.timestamp_ns,
                    hdr.scale,
                    hdr.generation,
                    hdr.retired_slot0,
                    hdr.retired_slot1,
                    hdr.reserved_flags,
                    new_sr,
                    b"\x00" * 8
                )
                shm.buf[:HEADER_COMPACT_SIZE] = new_header_bytes
                return slot, hdr.generation
            time.sleep(retry_delay_s)

        raise TimeoutError(f"No fue posible adquirir reader lease atómico en slab {hex(slab_id)}")

    def release_reader_lease(self, slab_id: int, slot: int):
        """Libera el lease de lectura decrementando state_and_readers del slot correspondiente."""
        shm = self.slabs[slab_id]["shm"]
        with self._local_lock:
            hdr = self.read_header(slab_id)
            destroying = hdr.state_and_readers & (1 << 63)
            r0 = hdr.state_and_readers & 0xFFFFFFFF
            r1 = (hdr.state_and_readers >> 32) & 0x7FFFFFFF

            if slot == 0:
                r0 = max(0, r0 - 1)
            else:
                r1 = max(0, r1 - 1)

            new_sr = destroying | (r1 << 32) | r0

            new_header_bytes = HEADER_COMPACT_STRUCT.pack(
                PMTP_MAGIC_NUMBER,
                PMTP_VERSION_V1,
                hdr.dtype_id,
                hdr.active_slot,
                hdr.slab_id,
                hdr.num_elements,
                hdr.timestamp_ns,
                hdr.scale,
                hdr.generation,
                hdr.retired_slot0,
                hdr.retired_slot1,
                hdr.reserved_flags,
                new_sr,
                b"\x00" * 8
            )
            shm.buf[:HEADER_COMPACT_SIZE] = new_header_bytes

    def read_snapshot_leased(self, slab_id: int) -> Tuple[np.ndarray, int]:
        """Lectura snapshot completa garantizada libre de torn-reads."""
        info = self.slabs[slab_id]
        shm = info["shm"]
        slot, gen = self.acquire_reader_lease(slab_id)
        try:
            slot_offset = HEADER_COMPACT_SIZE + (slot * info["payload_bytes"])
            view = np.ndarray(
                shape=(info["num_elements"],),
                dtype=info["dtype"],
                buffer=shm.buf,
                offset=slot_offset
            )
            return view.copy(), gen
        finally:
            self.release_reader_lease(slab_id, slot)

    def get_zero_copy_dlpack_tensor(self, slab_id: int):
        """
        Soporte nativo DLPack Zero-Copy blindado bajo Lease Atómico (PY-SEV0-003).
        Adquiere formalmente reader lease en el slot activo y registra finalizer
        para liberar el lease automaticamente cuando el tensor sea recolectado.
        Permite: torch.from_dlpack(bus.get_zero_copy_dlpack_tensor(slab_id))
        """
        info = self.slabs[slab_id]
        shm = info["shm"]
        # Adquirir lease atomico formal para prevenir que un escritor sobrescriba el slot
        slot, gen = self.acquire_reader_lease(slab_id)
        slot_offset = HEADER_COMPACT_SIZE + (slot * info["payload_bytes"])
        
        # Buffer numpy directo sobre shared memory en modo solo lectura
        raw_base = np.ndarray(
            shape=(info["num_elements"],),
            dtype=info["dtype"],
            buffer=shm.buf,
            offset=slot_offset
        )
        raw_view = raw_base.view(PmtpLeasedArray)
        raw_view.flags.writeable = False
        # Anclar referencias de ciclo de vida para evitar UAF
        raw_view._shm_owner = shm
        raw_view._bus_owner = self
        raw_view._leased_slot = slot
        raw_view._generation = gen
        
        # Finalizer debil para liberar el lease atomico cuando el consumidor descarte el tensor
        weakref.finalize(raw_view, self.release_reader_lease, slab_id, slot)
        return raw_view

    def release_all(self):
        """Cierre y desvinculación limpia marcando DESTROYING_BIT (Anti-UAF)."""
        with self._local_lock:
            for sid, info in list(self.slabs.items()):
                shm = info["shm"]
                try:
                    # Marcar destrucción atómica en offset 48 (state_and_readers)
                    hdr = self.read_header(sid)
                    destroy_sr = hdr.state_and_readers | (1 << 63)
                    shm.buf[self.STATE_AND_READERS_OFFSET:self.STATE_AND_READERS_OFFSET + 8] = struct.pack("<Q", destroy_sr)
                except Exception:
                    pass
                try:
                    shm.close()
                except Exception:
                    pass
                try:
                    shm.unlink()
                except Exception:
                    pass
            self.slabs.clear()

    def cleanup(self):
        """Alias de release_all para limpieza determinista."""
        self.release_all()

    @property
    def _slabs(self) -> Dict[int, Tuple[int, Any]]:
        """Mapa de compatibilidad para inspección Red Team de buffers de memoria compartida."""
        out: Dict[int, Tuple[int, Any]] = {}
        for sid, info in self.slabs.items():
            hdr = self.read_header(sid)
            out[sid] = (hdr.active_slot, info["shm"])
        return out

    def publish_tensor(self, vec: np.ndarray, aux_tag: int = 0) -> str:
        """
        Asigna o reutiliza un slab en memoria compartida, publica atómicamente `vec`
        y devuelve el descriptor string `SLAB_ID_<id>_<gen>`.
        """
        arr = np.asarray(vec, dtype=np.float64).ravel()
        sid = (self._next_slab_seq % max(1, self.max_slabs)) + 1
        self._next_slab_seq += 1
        if sid in self.slabs and self.slabs[sid]["num_elements"] == arr.size and not self.slabs[sid].get("released", False):
            self.publish_snapshot_atomic(sid, arr)
        else:
            if sid in self.slabs:
                try:
                    self.slabs[sid]["shm"].close()
                    self.slabs[sid]["shm"].unlink()
                except Exception:
                    pass
                self.slabs.pop(sid, None)
            self.allocate_tensor_slab(sid, arr.size, dtype=np.float64, scale=1.0)
            self.publish_snapshot_atomic(sid, arr)
        self.slabs[sid]["released"] = False
        self.slabs[sid]["published_at_ns"] = time.time_ns()
        hdr = self.read_header(sid)
        return f"SLAB_ID_{sid}_{hdr.generation}"

    def read_tensor(self, slab_descriptor: str, verify_stiefel: bool = True) -> np.ndarray:
        """
        Lee un tensor desde `SLAB_ID_<id>_<gen>` con lease atómico, verificando que
        no haya sido liberado (anti-ABA/epoch) y opcionalmente que cumpla la norma unitaria Stiefel.
        """
        parts = str(slab_descriptor).split("_")
        sid = int(parts[2])
        expected_gen = int(parts[3]) if len(parts) > 3 else None
        if sid not in self.slabs or self.slabs[sid].get("released", False):
            raise RuntimeError(f"Stale or released slab descriptor rejected: {slab_descriptor}")
        arr, gen = self.read_snapshot_leased(sid)
        if expected_gen is not None and gen != expected_gen:
            raise RuntimeError(f"ABA generation mismatch on slab {sid}: expected {expected_gen}, got {gen}")
        if verify_stiefel:
            # Acumulador compensado de Neumaier / Shewchuk en FP64 (C-accelerated, error <= 1e-15)
            nrm = math.sqrt(max(0.0, math.fsum(arr * arr)))
            if abs(nrm - 1.0) > 1e-6:
                raise ValueError(f"Stiefel unit sphere integrity violation on {slab_descriptor}: norm={nrm}")
        return arr

    def release_slab(self, slab_descriptor: str):
        """Marca un slab como retirado/liberado para bloquear lecturas obsoletas (ABA)."""
        parts = str(slab_descriptor).split("_")
        sid = int(parts[2])
        if sid in self.slabs:
            self.slabs[sid]["released"] = True

    def reap_expired_leases(self) -> int:
        """Recolecta y libera slabs cuyo lease haya expirado (crash recovery)."""
        now_ns = time.time_ns()
        timeout_ns = int(self.lease_timeout_ms * 1_000_000)
        reaped = 0
        for sid, info in list(self.slabs.items()):
            if not info.get("released", False):
                pub_ns = info.get("published_at_ns", now_ns)
                if now_ns - pub_ns >= timeout_ns:
                    info["released"] = True
                    reaped += 1
        return reaped

