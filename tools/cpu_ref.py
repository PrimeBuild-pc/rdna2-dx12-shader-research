"""Reference CPU di s4_pressure, in float32, per validare che la baseline GPU calcoli
davvero quello che l'HLSL dice.

Legge l'input dumpato dal banco (stessi bit letti dalla GPU), replica la semantica dello
shader e confronta con out_baseline.bin.

    python tools/cpu_ref.py <dumpdir> <dataset> [n_threads]

Nota: sin/cos GPU sono approssimazioni hardware; una divergenza dell'ordine di 1e-6
relativo e' attesa e non indica un bug. Su input con argomenti grandi la riduzione di
range diverge molto di piu': lo riportiamo, non lo nascondiamo.
"""
import sys
import numpy as np

N_IN = 65536          # elementi float4 realmente letti (indice & 65535)


def cpu_ref(inp, n):
    """inp: (65536,4) float32. Restituisce (n,4) float32."""
    t = np.arange(n, dtype=np.int64)
    v = np.empty((24, n, 4), dtype=np.float32)
    for i in range(24):
        v[i] = inp[(t * 24 + i) & (N_IN - 1)] * np.float32(i + 1)
    for k in range(24):                     # sequenziale: dipendenze loop-carried
        v[k] = np.sin(v[k]) + v[(k * 7) % 24] * np.cos(v[(k * 13) % 24])
    s = np.zeros((n, 4), dtype=np.float32)
    for j in range(24):
        s += v[j] * v[(j * 5) % 24]
    return s


def report(ref, gpu):
    a = ref.reshape(-1).astype(np.float64)
    b = gpu.reshape(-1).astype(np.float64)
    m = np.isfinite(a) & np.isfinite(b)
    nan_div = int(np.count_nonzero(np.isnan(a) != np.isnan(b)))
    inf_div = int(np.count_nonzero(np.isinf(a) != np.isinf(b)))
    print(f"  elementi           {a.size}")
    print(f"  finiti in entrambi {int(m.sum())} ({100.0*m.sum()/a.size:.2f}%)")
    print(f"  NaN divergenti     {nan_div}")
    print(f"  Inf divergenti     {inf_div}")
    if not m.any():
        print("  (nessun elemento finito: confronto numerico non significativo)")
        return
    d = np.abs(a[m] - b[m])
    den = np.maximum(np.abs(a[m]), np.abs(b[m]))
    sig = den > 1e-30
    print(f"  max abs err        {d.max():.6e}")
    print(f"  max rel err        {np.max(d[sig]/den[sig]) if sig.any() else 0.0:.6e}")
    print(f"  RMS err            {np.sqrt(np.mean(d*d)):.6e}")
    print(f"  RMS rel            {np.sqrt(np.mean(d*d))/np.sqrt(np.mean(a[m]**2)):.6e}")
    print(f"  mediana |ref|      {np.median(np.abs(a[m])):.6e}")


def main():
    d, ds = sys.argv[1], int(sys.argv[2])
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 65536
    inp = np.fromfile(f"{d}\\in_ds{ds}.bin", dtype=np.float32).reshape(-1, 4)
    assert inp.shape[0] == N_IN, inp.shape
    gpu = np.fromfile(f"{d}\\out_ds{ds}.bin", dtype=np.float32).reshape(-1, 4)[:n]
    print(f"dataset {ds}, {n} thread confrontati")
    with np.errstate(over="ignore", invalid="ignore"):
        ref = cpu_ref(inp, n)
    report(ref, gpu)


if __name__ == "__main__":
    main()
