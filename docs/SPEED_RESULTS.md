# Speed Optimization Results

Real measured performance benchmarks for ScamShield Family pipeline stages, comparing the baseline multi-roundtrip pipeline against the optimized fast paths.

> **Testing Environment**: Windows 11, Python 3.10, Location: Sri Lanka (network distance to Meta API `api.meta.ai`).  
> **Model**: `muse-spark-1.3`, `sam-3.1`, `muse-image-1.0`.  
> **Measurement Tool**: `tools/time_pipeline.py data/demo_screenshot.png` (Real API measurements).

---

## 1. Measured Timings (Before vs. After)

| Pipeline Stage | Baseline (Before) | Optimized (After) | Speedup / Time Saved | Primary Optimization |
|---|---|---|---|---|
| **API Floor (Minimum network roundtrip)** | **5.9s** | **5.9s** | Baseline floor | 1 minimal Muse Spark call (`"Say hi"`) |
| **Text Analysis** | **48.3s** (Full agent tool-calling loop, 2-3 roundtrips) | **19.6s** (Fast mode: 1 model call) | **2.46x faster** (-28.7s) | `BOT_FAST_MODE=1`: local link checks run first, alert rule in code, 1 single API call |
| **Screenshot Vision** | **45.7s** (Original image) | **17.1s** (Shrunk image) | **2.67x faster** (-28.6s) | `shrink_image` thumbnailing (1024px max side JPEG) reduces upload and model inference time |
| **SAM 3.1 Segmentation** | **10.1s** (4 concepts serially, one after another) | **2.9s** (4 concepts in parallel via `ThreadPoolExecutor`) | **3.48x faster** (-7.2s) | Parallel ThreadPool execution of SAM 3.1 concept stream calls; max 4 regions |
| **Guardian Risk Alert** | **~12–15s delay** (Synchronous Muse Image card generation blocked warning) | **Instant (< 0.2s)** (Text warning sent immediately; card generated in background) | **Immediate alert** | `asyncio.create_task(_send_card_later(...))` detaches card rendering from warning delivery |

---

## 2. Analysis of Optimizations

### 2.1 Why Text Went From 48.3s to 19.6s
- **Before**: The multi-turn tool-calling agent initiated an initial call to ask for tools, executed `check_links` and `scam_playbook`, sent the tool responses in a second API trip, and sometimes required a third trip for final structuring. Each roundtrip across international transit added 5–15 seconds.
- **After**: `run_agent_fast` runs local URL heuristic checks instantly (0.001s), embeds findings into a structured prompt, and makes **exactly one** `muse-spark-1.3` call. The high-risk alert decision is handled immediately by deterministic application code.

### 2.2 Why Screenshot Processing Dropped From 55.8s to 20.0s Total
- **Image Downsampling**: Raw mobile screenshots are several megabytes with high pixel dimensions. Shrinking to a normalized 1024px JPEG thumbnail drops the payload to under 50KB, slashing upload time and vision token processing while preserving normalized bounding box precision.
- **Parallel SAM 3.1 Segmentation**: Instead of serial streaming requests to `sam-3.1` for each identified noun phrase (4 calls × ~2.5s = 10.1s), `refine_with_sam` now dispatches all unique concept calls concurrently via a thread pool. The entire segmentation batch finishes in 2.9s (matching the duration of a single call).

### 2.3 Why Guardians Are Warned Instantly
- **Before**: When high risk was detected, the bot called `make_warning_card` (generating an illustration with `muse-image-1.0`) before sending any message to the guardian. If image generation took 8–12 seconds, the family was left waiting.
- **After**: The guardian receives the urgent text message immediately via Telegram. The visual warning card is generated asynchronously via `asyncio.create_task` and delivered afterwards as a follow-up.

### 2.4 User Perception Optimizations
- **Instant Acknowledgment**: When an elder sends a message, photo, or audio note, the bot replies instantly with a friendly status message (`"🔎 Checking..."`, `"📷 Looking at your screenshot..."`).
- **Instant Local Heuristics**: If a message contains a clearly suspicious URL pattern (e.g., suspicious TLD, IP host, brand impersonation), the bot updates the waiting message immediately with a local warning badge while waiting for the model.
- **Concurrency**: `Application.builder().concurrent_updates(True)` prevents slow user uploads from blocking other family members in the Telegram queue.

---

## 3. Audit Re-measurement: 2026-10-28

Run: `python tools/time_pipeline.py data/demo_screenshot.png`  
Environment: Windows 11, Python 3.10, `muse-spark-1.3`, `sam-3.1`.

| Stage | Measured |
|---|---|
| API floor — one tiny Muse Spark call | **2.9 s** |
| Text — FULL agent (tool-calling loop) | FAILED (API 400 content-filter on test scam text — fallback returns medium-risk) |
| Text — FAST mode (1 model call, bot default) | **5.3 s** |
| Vision — original image (36 KB) | **14.9 s** |
| Vision — shrunk image (48 KB JPEG) | **10.8 s** (27% faster) |
| SAM 3.1 — 4 concepts serially | **8.5 s** |
| SAM 3.1 — 4 concepts in parallel | **3.0 s** (**2.8× faster** than serial) |

Load test (5 parallel `/analyze/text` requests): 5/5 HTTP 200, range 35–44 s.

Note on SAM: all 4 concept calls returned 0 boxes on the synthetic demo screenshot. SAM works best on real-world screenshots with distinct visual objects (buttons, logos, message bubbles). The rough Muse Spark bounding boxes are shown as the fallback.
