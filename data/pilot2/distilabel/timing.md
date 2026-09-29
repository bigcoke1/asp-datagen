# Timing: distilabel (datagen.distil_run)

- Machine: Apple M4 Pro, 48 GB, macOS 26.7, Ollama 0.33.3
- Models: `qwen3.8:27b` (27.3B Q4_K_M), `gemma4:31b` (31.3B Q4_K_M)
- Settings: 2 categories, k=3 samples x 2 teachers, 1 calls in flight, batches of 50
- **20 bundles in 81.5 min**: 244 s per bundle, so about 67.9 h per 1,000 bundles at these settings.
- LLM calls: 212. Time with at least one call running: 81.3 min; with none: 8 s.

| stage | model | calls | active | median call | p95 call | prompt time | output tokens | output time | model loads |
|---|---|---|---|---|---|---|---|---|---|
| surface | `qwen3.8:27b` | 15 | 13.8 min | 55.0 s | 70.9 s | 51 s | 4,769 | 12.8 min | 1 (4 s) |
| surface | `gemma4:31b` | 5 | 3.2 min | 42.3 s | 42.6 s | 20 s | 1,809 | 2.7 min | 1 (8 s) |
| label | `gemma4:31b` | 96 | 22.3 min | 5.3 s | 48.2 s | 14.7 min | 4,974 | 7.6 min | 0 (0 s) |
| label | `qwen3.8:27b` | 96 | 42.1 min | 19.5 s | 54.9 s | 14.9 min | 8,742 | 27.0 min | 1 (10 s) |
