Vector index & ML setup

This project supports optional vector search (embeddings + FAISS) used by the AI search endpoints. Because native wheels for FAISS and some ML packages can be fragile on Windows, the code includes safe fallbacks so the web app runs even when heavy ML deps are missing.

Recommended approaches

- Fast / reliable (recommended for development & CI): use the provided lightweight tests and the simulated job path. This requires only Python + the packages in `requirements.txt` and avoids installing FAISS locally.
- Full-featured (embeddings + FAISS): use a conda environment with prebuilt wheels matching your platform. See the conda steps below.

Conda (recommended) setup

1) Create and activate a conda environment (Linux or Windows with conda):

```powershell
conda create -n citizen-ml python=3.11 -y
conda activate citizen-ml
```

2) Install packages (prefer conda-forge where possible):

```powershell
conda install -c conda-forge python=3.11 pip numpy=2.3.4 -y
pip install -r citizen-portal/requirements.txt
# If you need faiss-cpu, prefer conda-forge wheel there:
conda install -c conda-forge faiss-cpu -y
```

Notes about FAISS and NumPy compatibility

- FAISS is a compiled library and must match the ABI of your NumPy / Python installation. Using conda-forge to install both NumPy and faiss-cpu together is the most reliable approach.
- On Windows, installing faiss-cpu via pip is often unreliable due to binary wheel availability; prefer conda-forge or use a Linux container for production workloads.
- If FAISS fails to load at runtime, the app will fall back to saving embeddings to `data/embeddings.npy` and performing a NumPy matrix search instead (slower but pure Python / NumPy).

Quick 'try it' commands (safe, CI-friendly)

1) Use the simulated job to validate admin job lifecycle without ML deps:

```powershell
cd "G:/INTERNSHIP/task project"
# Run the Flask app in dev mode (or run the test suite directly)
python -m pytest -q tests/test_index_jobs.py::test_simulated_build_index_job
```

2) Run the full test suite (includes ai_search fallback tests):

```powershell
python -m pytest -q
```

Building the real index (only if you have embeddings model installed)

1) Ensure `sentence-transformers` and a compatible `numpy` are installed (prefer conda). Then run:

```powershell
cd citizen-portal
# As admin in the app, POST to /api/admin/build_index or run the CLI helper
python scripts\build_index.py
```

2) Successful builds will write metadata to `data/faiss_meta.json` and either `data/faiss.index` (FAISS) or `data/embeddings.npy` (NumPy fallback).

Scheduler (periodic rebuilds)

- To enable daily rebuilds, set `ENABLE_INDEX_SCHEDULER=true` (and optionally `INDEX_BUILD_INTERVAL_HOURS`) before starting the Flask process. The app attempts to start APScheduler if available and will log the scheduler startup; if APScheduler isn't installed the app continues to run without scheduling.

Testing & CI

- This repo includes a lightweight pytest suite that uses a simulated index-build job (no heavy ML deps). The GitHub Actions workflow in `.github/workflows/ci.yml` runs the test suite on push/PR.

Troubleshooting

- If you see import or DLL load errors referencing faiss, numpy, or tokenizers:
  - Prefer creating a conda env and installing from conda-forge.
  - For Windows development, consider using the simulated job/tests for CI and a Linux container for heavy ML tasks.

Security

- Keep LLM API keys (e.g., `OPENROUTER_API_KEY`) out of source control and set them as environment variables on your host/CI.

Contact / notes

- If you want, I can add a small Dockerfile that uses a conda-based image to produce a reproducible environment for building the FAISS-backed index (recommended for production).
