# Data that is not in git

To rebuild the whole environment (tools, versions, drivers, data to recapture), see [docs/REBUILD.md](../docs/REBUILD.md) and [manifests/environment.json](manifests/environment.json).

Git holds every text file up to 5 MB (reports, CSV/JSON results, logs, HLSL sources, tools). Two
manifests cover everything else, each line with path, size and SHA-256 taken from the original
working copy:

| Manifest | What it lists |
|---|---|
| [manifests/release_data_files.csv](manifests/release_data_files.csv) | Files in the release archives below; the `archive` column says which one. |
| [manifests/excluded_files.csv](manifests/excluded_files.csv) | Files not published at all, with the reason (third-party binary, game-derived data, raw ETL trace, build artifact, verbose MSBuild log). |

## Release archives

Download from the
[v1.0-archive release](https://github.com/PrimeBuild-pc/rdna2-dx12-shader-research/releases/tag/v1.0-archive)
and extract every asset **at the repository root** (`7z x <asset>`): the archives keep the `research/...` paths, so the files land
next to the reports that reference them. `.gitignore` already ignores them.

| Archive | Contents |
|---|---|
| `large-measurement-data.zip` | PresentMon CSVs (Fortnite, Cyberpunk), WPR offline analysis outputs (GPU queue replay, wait packets, DMA spans), WPA CSV export of the smoke trace, shader-container probe results. |
| `wpr-etw-event-exports.zip` | `events.tsv` (superseded) and `events_v2.tsv` (canonical): full TDH event extraction of the Cyberpunk WPR trace. |
| `oracle-frame-dumps.7z` | 280 raw frame dumps (`*.bin`, 2.1 GB uncompressed) used as image-correctness oracles in phases 2O–2U. All from open-source samples. |
| `msbuild-diagnostic-logs.7z` | 59 verbose MSBuild logs (0.8 GB uncompressed) of the MiniEngine variant builds. |
| `extra-analysis-data.7z` | GPU event JSONL from the WPR replay, plus the temp-folder scratch notes and sources from September (`preserved_temp_claude_20260909/driver-mod-temp-source-notes/`; another project's folder and agent cache files were removed, so it differs from the zip hash in that folder's README). |

Check the files after unzipping:

```bash
python - <<'EOF'
import csv, hashlib
for r in csv.DictReader(open("data/manifests/release_data_files.csv")):
    h = hashlib.sha256(open(r["path"], "rb").read()).hexdigest()
    print("OK " if h == r["sha256"] else "BAD", r["path"])
EOF
```

## Not published

- **WPR `.etl` traces** (21 GB for the Cyberpunk run, SHA-256
  `e2e4ae42ccb8bb1e41d8717513abe1bb469d6e4969ef1b8e363f229a5b21e739`). Too large to host.
- **Cyberpunk 2077 shader caches, extracted DXIL/LLVM IR, and the compiled add-on payloads**:
  CD PROJEKT RED content. To reproduce phases 64–69, copy the caches from your own install and
  check them against the hashes in the excluded manifest and in each phase's `artifact_manifest.json`.
- **Third-party binaries**: AMD driver package and installer (Adrenalin 26.9.1), Radeon Developer
  Tool Suite, Ghidra, Sysinternals, ReShade, GPUPerfAPI and SDK DLLs, Microsoft public PDBs.
  Get them from their vendors.
- **Build outputs**: executables, `.obj`/`.lib`/`.pdb`, compiled `.cso`, add-on binaries.
  The build scripts and logs needed to rebuild them are in git.
