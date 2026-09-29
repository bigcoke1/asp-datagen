# Timing: plain Python (datagen.run), one call at a time

- Machine: Apple M4 Pro, 48 GB, macOS 26.7, Ollama 0.33.3
- Models: `qwen3.8:27b` (27.3B Q4_K_M), `gemma4:31b` (31.3B Q4_K_M)
- Settings: 2 categories, k=3 samples x 2 teachers
- **20 bundles in 99.9 min**: 300 s per bundle, so about 83.3 h per 1,000 bundles at these settings.
- LLM calls: 212. Time with at least one call running: 99.9 min; with none: 0 s.

| stage | model | calls | active | median call | p95 call | prompt time | output tokens | output time | model loads |
|---|---|---|---|---|---|---|---|---|---|
| surface | `qwen3.8:27b` | 15 | 15.4 min | 60.9 s | 77.1 s | 50 s | 4,944 | 13.2 min | 15 (84 s) |
| label | `qwen3.8:27b` | 96 | 47.4 min | 18.4 s | 58.1 s | 19.3 min | 8,640 | 26.5 min | 17 (90 s) |
| label | `gemma4:31b` | 96 | 34.2 min | 5.5 s | 57.9 s | 23.8 min | 4,980 | 7.8 min | 32 (151 s) |
| surface | `gemma4:31b` | 5 | 3.0 min | 40.3 s | 43.8 s | 20 s | 1,756 | 2.6 min | 0 (0 s) |
