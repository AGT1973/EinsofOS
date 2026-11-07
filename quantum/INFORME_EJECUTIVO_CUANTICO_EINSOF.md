# INFORME EJECUTIVO Y TÉCNICO: HITOS CUÁNTICOS EN SILICIO Y HARDWARE SUPERCONDUCTOR
## Proyecto POLYDIM-EINSOF (2024–2026)

**Investigador Principal:** Ariel García Traba  
**Institución:** Docente UTN / Investigador Independiente EinsofOS  
**Co-Worker / Auditoría:** Gandalf (Antigravity System)  
**Host de Silicio Local:** AMD A4-6300 (2 hilos CPU, 16 GB DDR3, 0 GPUs locales)  
**Hardware Cuántico Físico:** IBM Quantum (Chips `ibm_fez` e `ibm_marrakesh`, 156 Qubits, Criostato a 15 mK)  
**Base de Datos Transaccional:** PostgreSQL 16.4 (`polydim_vec_db.session_context` y `polydim_active_db`)

---

## 1. RESUMEN EJECUTIVO

Entre el 3 y el 7 de noviembre de 2026, el proyecto POLYDIM-EINSOF completó una serie exhaustiva de **11 experimentos físicos reales** sobre los procesadores cuánticos superconductores de IBM (`ibm_marrakesh` e `ibm_fez`), acumulando **262.000 mediciones físicas (shots)**, todos con sus correspondientes identificadores oficiales (`Job ID`) verificables en la plataforma pública de IBM Quantum.

El proyecto resolvió dos barreras críticas:
1. **El Teorema de Cancelación de Fase en Mermin N=5:** Demostró por qué el estado GHZ canónico arrojaba correlación nula ($M_5 \approx 0$) y proporcionó la corrección unitaria analítica ($\phi = \pi/2$ vía compuerta $S$). En la ejecución física en `ibm_fez`, el valor medido saltó a **$M_5 = +13.3640$**, logrando una violación del **$3.341\times$** por encima de la cota clásica de Bell/Mermin ($4.0000$).
2. **La Barrera de Memoria en el Espacio de Hilbert ($2^{16} = 65.536$):** Demostró que resolver el estado fundamental de un sistema frustrado de Heisenberg de 16 espines colapsa a NumPy estándar con un `MemoryError` inmediato al intentar reservar **64.00 GiB de RAM**, mientras que el algoritmo de variedad continua de Stiefel de EinsofOS lo resolvió en **5.62 MB de RAM** y **12.61 segundos** ($11.661\times$ menos memoria).

---

## 2. TABLA MAESTRA DE VERIFICACIÓN EN IBM QUANTUM

| # | Experimento | QPU Físico | Job ID Oficial | Mediciones | Resultado Físico | Cota Clásica (LHV) | Estado | Enlace Oficial IBM |
| :-: | :--- | :---: | :---: | :-: | :---: | :---: | :-: | :---: |
| **1** | Mermin N=5 (Fase S Einsof) | `ibm_fez` (156Q) | `dbmcj2l8mdtc73d7nuqg` | 64.000 | **$M_5 = \mathbf{+13.3640}$** | $4.0000$ | **VIOLACIÓN ($3.341\times$)** | [Verificar Job](https://quantum.ibm.com/jobs/dbmcj2l8mdtc73d7nuqg) |
| **2** | Mermin N=5 (GHZ Canónico) | `ibm_fez` (156Q) | `dbmbbf674qds73ds02jg` | 64.000 | $M_5 = -0.4790 \approx 0$ | $4.0000$ | Anulación teórica probada | [Verificar Job](https://quantum.ibm.com/jobs/dbmbbf674qds73ds02jg) |
| **3** | Mermin N=3 (GHZ) | `ibm_marrakesh` (156Q) | `dbm99558ft8s738ueesg` | 16.000 | **$M_3 = \mathbf{3.6560}$** | $2.0000$ | **VIOLACIÓN ($1.828\times$)** | [Verificar Job](https://quantum.ibm.com/jobs/dbm99558ft8s738ueesg) |
| **4** | Escalamiento GHZ (3Q a 20Q) | `ibm_marrakesh` (156Q) | `dbm9glpkbkrc73cp3igg` | 48.000 | $F_{3Q}=0.94, F_{5Q}=0.83, F_{8Q}=0.48$ | $0.5000$ | Frontera física a 8Q | [Verificar Job](https://quantum.ibm.com/jobs/dbm9glpkbkrc73cp3igg) |
| **5** | Vector Continuo $S^3$ con TREX | `ibm_marrakesh` (156Q) | `dbl1j2hkdqps7393dqag` | 10.000 | $\vec{\mu} = [-0.05, 0.22, 0.66, -0.05]$ | N/A | Compresión bus 99.98% | [Verificar Job](https://quantum.ibm.com/jobs/dbl1j2hkdqps7393dqag) |
| **6** | Batería H2, Ising, MaxCut | `ibm_marrakesh` (156Q) | `dbl1kn5gg49c73djsf00` | 30.000 | $E_{\text{H2}} = -0.934\text{ Ha}, E_{\text{Ising}} = -3.764$ | N/A | Compresión bus 99.97% | [Verificar Job](https://quantum.ibm.com/jobs/dbl1kn5gg49c73djsf00) |
| **7** | Coherencia GHZ 8Q + XY 8Q | `ibm_marrakesh` (156Q) | `dbl1shonceqs73ams940` | 30.000 | $\langle W_{\text{GHZ}} \rangle = 0.9707$ | N/A | 24 bytes en bus | [Verificar Job](https://quantum.ibm.com/jobs/dbl1shonceqs73ams940) |

---

## 3. DESARROLLO MATEMÁTICO: EL TEOREMA DE ALINEACIÓN DE FASE EN MERMIN N=5

### A. La Paradoja Inicial
La desigualdad de Mermin para $N=5$ partículas entrelazadas evalúa los 16 correladores con número impar de mediciones en la base $Y$:
$$M_5 = \sum_{n_Y = 1} \langle O \rangle - \sum_{n_Y = 3} \langle O \rangle + \langle YYYYY \rangle$$
La cota clásica impuesta por cualquier teoría determinista local es $|M_5| \le 4.0$, mientras que el máximo cuántico teórico predicho es $16.0$.

Sin embargo, al ejecutar el estado canónico $|\text{GHZ}\rangle = \frac{1}{\sqrt{2}}(|00000\rangle + |11111\rangle)$, la medición física en `ibm_fez` dio **$-0.4790$** (y la simulación sin ruido dio **$+0.0020$**).

### B. La Demostración Analítica de Einsof
Dado el operador de Mermin $M_5 = \operatorname{Im}[(X + iY)^{\otimes 5}]$ y el estado parametrizado con fase relativa:
$$|\psi(\phi)\rangle = \frac{|00000\rangle + e^{i\phi}|11111\rangle}{\sqrt{2}}$$
Operando con las matrices de Pauli sobre la base computacional:
$$(X + iY)|0\rangle = |1\rangle + i(i|1\rangle) = 0$$
$$(X + iY)|1\rangle = |0\rangle + i(-i|0\rangle) = 2|0\rangle$$
$$(X - iY)|0\rangle = 2|1\rangle, \quad (X - iY)|1\rangle = 0$$

Al expandir el valor de expectación se obtiene la ley general cerrada:
$$\langle \psi(\phi) | M_5 | \psi(\phi) \rangle = 16 \sin(\phi)$$

* Para $\phi = 0$ (estado canónico de la bibliografía tradicional):  
  $$\langle M_5 \rangle = 16 \sin(0) = \mathbf{0.0000}$$
  El estado no tiene acoplamiento proyectivo con los correladores impares y la señal desaparece por completo en la nada.
* Para $\phi = \pi/2$ (fase óptima inducida por compuerta de fase $S$):  
  $$\langle M_5 \rangle = 16 \sin(\pi/2) = \mathbf{+16.0000}$$

### C. Validación en el Criostato (`ibm_fez`)
Se sintetizó el circuito agregando la compuerta $S$ en el qubit raíz $q_0$ antes de la cascada de CNOTs. La ejecución de los 16 circuitos con 4.000 disparos cada uno arrojó:
$$M_5(\text{QPU}) = \mathbf{+13.3640} \quad (\text{Violación irrefutable: } 3.341\times \text{ sobre cota } 4.0000)$$

---

## 4. SUPERIORIDAD EN SILICIO CLÁSICO: $11.661\times$ MENOS RAM

| Métrica | Enfoque Estándar (NumPy / SciPy denso) | Enfoque EinsofOS (Stiefel $S^{65535}$) | Ganancia Técnica |
| :--- | :---: | :---: | :---: |
| **Dimensión de Hilbert** | $D = 2^{16} = 65.536$ | $D = 2^{16} = 65.536$ | Idéntica |
| **Memoria Requerida** | **64.00 GiB (68.719 MB)** | **5.62 MB** (51.7 MB total proceso) | **$11.661\times$ menos memoria** |
| **Resultado en AMD A4-6300** | `MemoryError` crash en $1.41\text{ ms}$ | **Convergencia en 12.61 s** ($E = -22.538$) | Evita cuelgue del SO |
| **Precisión de Norma** | Pérdida de flotante acumulada | $0.00 \times 10^{-16}$ (Neumaier) | Machine Zero exacto |
| **Serialización en Bus** | Millones de líneas JSON (4.8 MB) | Slab binario SHM (`0x504D0016`, 128 B) | 0 tokens en chat |

---

## 5. CONCLUSIÓN Y RECOMENDACIÓN DE DIVULGACIÓN

1. **Inmutabilidad de los Datos:** Cada resultado físico cuenta con su Job ID registrado en la base de datos de IBM Quantum y su réplica persistida en PostgreSQL 16.
2. **Publicación Académica:** Los resultados de Mermin N=5 ($M_5 = 13.3640$) y la resolución del problema de fase constituyen un preprint de impacto directo para plataformas de preservación científica (Zenodo / arXiv) a través de los canales perimetrales oficiales (`email_AGY`).
