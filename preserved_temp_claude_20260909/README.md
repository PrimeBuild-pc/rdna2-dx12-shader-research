# Recupero dati da Temp\claude — 2026-09-09

Creato prima della pulizia di `%LOCALAPPDATA%\Temp\claude`.

## Contenuto preservato

- `dxs-tracked-changes.patch`: modifiche tracciate del clone DirectX Graphics Samples.
- `dxs-untracked/`: quattro sorgenti nuovi e due DLL GPUPerfAPI.
- `dxs-status.txt`: commit base, remote e stato Git.
- `driver-mod-temp-source-notes.zip`: scratchpad della sessione `driver mod` e sorgenti/configurazioni/note degli esperimenti; esclusi build, vcpkg, pacchetti e dipendenze rigenerabili.

Archivio verificato: 11200 file, 175.3 MiB non compressi.
SHA-256: `2dc2fce13387a4d99b0ff1ec70319ee8f34a22c725f4cdd6ccc7381ca6c502f6`

## Ripristino patch

```powershell
git clone https://github.com/microsoft/DirectX-Graphics-Samples.git
git -C DirectX-Graphics-Samples checkout 213dd4fd4918ea009dd8f35adee1aff1f2ecaba4
git -C DirectX-Graphics-Samples apply --binary "dxs-tracked-changes.patch"
```

Poi copiare il contenuto di `dxs-untracked` nella radice del clone.
