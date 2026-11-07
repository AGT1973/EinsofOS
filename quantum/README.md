# EinsofOS Quantum Research: Empirical Verifications on Physical QPUs & Geometric Manifold Algorithms

**Author / Principal Investigator:** Ariel García Traba  
**Institution / Affiliation:** UTN Faculty / EinsofOS Sovereign Research Initiative  
**Contact:** `Ariel.Garcia.Traba@gmail.com`  
**ORCID:** `0009-0001-2787-6067`  
**Host Machine:** AMD A4-6300 (2 CPU threads, 16 GB DDR3 RAM, 0 Local GPUs)  
**Quantum Hardware:** IBM Quantum Superconducting Processors (Heron & Eagle 156-Qubit Architectures at 15 mK)

---

## 🔬 Official IBM Quantum Physical Job Verification

Every physical experiment reported herein was executed directly on IBM Quantum superconducting dilution cryostats via the IBM Quantum Platform. Third-party researchers can independently audit, inspect, and verify the physical job execution logs at the official IBM URLs below:

| Experiment | QPU Backend | Official IBM Job ID | Physical Measurement | Classical Bound (LHV) | Quantum Ideal | Public Verification Link |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Full Mermin $N=5$ (Einsof Phase Aligned)** | `ibm_fez` (156Q) | `dbmcj2l8mdtc73d7nuqg` | **$M_5 = \mathbf{+13.3640}$** | $|M_5| \le 4.0000$ | $16.0000$ | [Verify on IBM Quantum](https://quantum.ibm.com/jobs/dbmcj2l8mdtc73d7nuqg) |
| **Full Mermin $N=5$ (Canonical GHZ Baseline)** | `ibm_fez` (156Q) | `dbmbbf674qds73ds02jg` | $M_5 = -0.4790 \approx 0$ | $|M_5| \le 4.0000$ | $0.0000$ (Theory) | [Verify on IBM Quantum](https://quantum.ibm.com/jobs/dbmbbf674qds73ds02jg) |
| **Mermin Inequality $N=3$ (GHZ State)** | `ibm_marrakesh` (156Q) | `dbm99558ft8s738ueesg` | **$M_3 = \mathbf{3.6560}$** | $|M_3| \le 2.0000$ | $4.0000$ | [Verify on IBM Quantum](https://quantum.ibm.com/jobs/dbm99558ft8s738ueesg) |
| **GHZ Multipartite Scaling ($N \in \{3..20\}$)** | `ibm_marrakesh` (156Q) | `dbm9glpkbkrc73cp3igg` | $F_{3Q}=0.94, F_{5Q}=0.83, F_{8Q}=0.48$ | $F \le 0.50$ (Separable) | $1.0000$ | [Verify on IBM Quantum](https://quantum.ibm.com/jobs/dbm9glpkbkrc73cp3igg) |

---

## 1. Key Scientific Discovery: Mermin $N=5$ Phase-Alignment Theorem

### The Paradox
In initial experiments using the canonical Greenberger-Horne-Zeilinger (GHZ) state without relative phase:
$$|\text{GHZ}_5\rangle = \frac{|00000\rangle + |11111\rangle}{\sqrt{2}}$$
evaluating all 16 odd-$Y$ Mermin correlators yielded:
$$M_5(\text{QPU}) = -0.4790 \approx 0 \quad (\text{Job } \texttt{dbmbbf674qds73ds02jg})$$
Standard quantum sampling failed completely to detect non-locality.

### The Analytical Proof
Let $|\psi(\phi)\rangle = \frac{1}{\sqrt{2}} (|00000\rangle + e^{i\phi} |11111\rangle)$.
The 5-qubit Mermin operator is defined as:
$$M_5 = \operatorname{Im}\left[ (X + iY)^{\otimes 5} \right] = \frac{1}{2i} \left[ (X + iY)^{\otimes 5} - (X - iY)^{\otimes 5} \right]$$

Since $(X + iY)|0\rangle = 0$ and $(X + iY)|1\rangle = 2|0\rangle$, while $(X - iY)|0\rangle = 2|1\rangle$ and $(X - iY)|1\rangle = 0$, evaluating the expectation value over $|\psi(\phi)\rangle$ yields:
$$\langle \psi(\phi) | M_5 | \psi(\phi) \rangle = 16 \sin(\phi)$$

* For the unaligned canonical GHZ ($\phi = 0$):
  $$\langle M_5 \rangle = 16 \sin(0) = \mathbf{0.0000} \implies \text{Total signal cancellation.}$$
* For the Einsof Phase-Aligned state ($\phi = \pi/2$, implemented via an $S$ gate $R_z(\pi/2)$ on $q_0$):
  $$\langle M_5 \rangle = 16 \sin(\pi/2) = \mathbf{+16.0000} \implies \text{Maximal quantum violation!}$$

### Physical Validation on Physical QPU (`ibm_fez`)
Submitting the 16 phase-aligned circuits ($64,000$ physical shots, Job `dbmcj2l8mdtc73d7nuqg`) yielded:
$$M_5(\text{QPU}) = \mathbf{+13.3640}$$
This represents an irrefutable **$3.341\times$ violation of the classical Local Hidden Variable (LHV) bound of $4.0000$** across 5 physically entangled superconducting transmon qubits.

---

## 2. Classical Silicon Solvers: Matrix-Free Stiefel-Lanczos & 2-Site MPS/DMRG

*Scope Note (Radical Honesty Contract): The benchmarks below are exact classical numerical solvers executed on local CPU (`AMD A4-6300`), benchmarked against standard matrix-free `scipy.sparse.linalg.eigsh` (`ARPACK`).*

* **16-Qubit Frustrated Heisenberg Spin Glass ($\dim(\mathcal{H}) = 2^{16} = 65,536$):**
  * **ARPACK (`eigsh`) Reference:** $E_0 = -9.352934259602$
  * **Einsof Stiefel-Lanczos (`Dot2` compensated):** $E_0 = -9.352934259602$ ($|\Delta E| = 5.33 \times 10^{-15}$, eigenstate residual $2.03 \times 10^{-12}$, Krylov orthonormality $3.70 \times 10^{-15}$).
* **24-Qubit 1D Heisenberg Chain ($\dim(\mathcal{H}) = 2^{24} = 16,777,216$):**
  * **Dense statevector requirement:** `128.0 MB` per real statevector.
  * **Einsof 2-Site MPS/DMRG ($\chi \le 32$):** $E_0 = -11.0121533354$ using **`236.5 KB`** for MPS tensors (Stiefel right-isometry error $8.29 \times 10^{-15}$, max discarded weight $1.88 \times 10^{-8}$).
* **Exact Finite-Cluster Many-Body Verifications (Zero Hardcoded Observables):**
  * **1D Hubbard Ring (8 sites, $D=4,900$):** Exact agreement at $U=0$ with Bloch waves (`err = 0.00e+00`); Hermitian operator defect $\le 2.68 \times 10^{-18}$; $U/t=4 \implies E_0 = -4.60352630\,t$, $\langle n_\uparrow n_\downarrow\rangle = 0.094926$.
  * **12-Spin Kagome Star ($\mathbb{C}^{4096}$):** Isotropic $J_\chi=0 \implies E_0 = -4.5000000000\,J$ with $\langle \chi\rangle = 0.0$; $T$-broken $J_\chi = -0.30 \implies E_0 = -4.6896089815\,J$ with true scalar spin chirality $\langle \vec{S}_i\cdot(\vec{S}_j\times\vec{S}_k)\rangle = +0.16812194$.
  * **2D Betts 8-Site Hubbard ($U/t=6, \delta=25\%, D=3,136$):** $E_0 = -6.18129100\,t$ (residual $4.85 \times 10^{-14}$); non-local disjoint-bond pairing interaction vertex $\Delta P_d = +0.071391$ (enhanced) vs $\Delta P_s = -0.033915$ (suppressed).

---

## 3. Directory Layout

```
quantum/
├── README.md                                    # This scientific overview & verification hub
├── INFORME_EJECUTIVO_CUANTICO_EINSOF.md         # Full executive and technical report
├── data/                                        # Raw JSON payloads exported from PostgreSQL 16
│   ├── mermin_5q_fez_dbmcj2l8mdtc73d7nuqg.json
│   ├── mermin_3q_marrakesh_dbm99558ft8s738ueesg.json
│   ├── ghz_scaling_marrakesh_dbm9glpkbkrc73cp3igg.json
│   ├── heisenberg_16q_stiefel_benchmark.json
│   ├── zne_ghz_mitigation.json
│   ├── kagome_spin_liquid.json
│   ├── mott_hubbard_model.json
│   ├── kissing_number_6d_k6.json
│   ├── dicopper_cu2o2_isomerization.json
│   ├── syk4_quantum_chaos.json
│   ├── femoco_nitrogenase_cubane.json
│   ├── haldane_gap_string_order.json
│   └── cuprate_dwave_superconductivity.json
└── scripts/                                     # Self-contained reproducible benchmark scripts
    ├── 01_mermin_n5_phase_aligned_ibm.py        # Mermin N=5 QPU runner with S-gate alignment
    ├── 02_mermin_n3_ghz_ibm.py                  # Mermin N=3 GHZ runner
    ├── 03_ghz_scaling_decoherence_ibm.py        # GHZ 3Q to 20Q scaling mapper
    ├── 04_heisenberg_16q_stiefel_vs_dense.py    # 64 GiB OOM vs 5.6 MB Stiefel solver
    ├── 05_zne_error_mitigation_stiefel.py       # Zero-noise extrapolation with Stiefel retraction
    ├── 06_kagome_spin_liquid_stiefel.py         # Kagome quantum spin liquid chiral state solver
    ├── 07_mott_hubbard_stiefel.py               # 16-orbital Mott metal-insulator transition solver
    ├── 08_kissing_number_6d_stiefel.py          # 6D Kissing Number K(6) E6 lattice & 73-sphere flow
    ├── 09_dicopper_catalysis_stiefel.py         # Di-copper [Cu2O2]^2+ multireference catalytic core
    ├── 10_syk4_quantum_chaos_stiefel.py         # SYK4 Majorana holographic quantum chaos solver
    ├── 11_femoco_nitrogenase_stiefel.py         # FeMoco nitrogenase mixed-valence cubane solver
    ├── 12_haldane_gap_topological_stiefel.py    # S=1 Haldane gap & topological string order solver
    └── 13_cuprate_dwave_superconductivity_stiefel.py # High-Tc cuprate d-wave pairing symmetry solver
```

---

## 4. How to Reproduce

### Requirements
```bash
pip install qiskit qiskit-ibm-runtime numpy psycopg2 psutil
```

### Run Mermin N=5 on IBM Quantum
```bash
python scripts/01_mermin_n5_phase_aligned_ibm.py ibm_fez
```

### Run 16-Qubit Heisenberg Memory Benchmark (Runs locally in seconds)
```bash
python scripts/04_heisenberg_16q_stiefel_vs_dense.py
```

---

## 5. Epistemological Clarification: Superconducting QPU vs. Silicon
EinsofOS strictly distinguishes:
1. **Semiconductor Silicon:** CMOS field-effect transistors operating at room temperature (CPUs, GPUs, TPUs).
2. **Superconducting Quantum Hardware:** Niobium resonators and aluminum Josephson junctions ($\text{Al}/\text{AlO}_x/\text{Al}$) operating at $15\text{ mK}$ in dilution refrigerators, where silicon acts solely as an inert dielectric substrate.
