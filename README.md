# PokeAI — Curiosity-Driven Autonomous Game Agent for Pokémon FireRed

A hybrid autonomous agent that plays Pokémon FireRed (GBA) through demonstration-guided Markov transition matching, hierarchical multi-context perceptron pipelines, intrinsic curiosity-driven exploration, and persistent cross-session knowledge accumulation. The system operates via a Lua–Python bridge through the BizHawk emulator, reading structured game state directly from GBA memory — no reward shaping, no pixel-level deep learning, and fully interpretable at every decision layer.

**Authors:** Angshuman Basu, Nathaniel Maw, Achal Mukkapati  
**Affiliation:** Khoury College of Computer Sciences, Northeastern University

---

## Repository Layout

Two pipelines (AI agent and human-demonstration recorder) share a single data root. All code reads and writes JSON under `jsons/` at the repo root (this matches `BASE_PATH` hardcoded in the notebooks and Lua scripts).

```
cogai/
├── README.md                       ← You are here
├── jsons/                          ← SHARED data root (matches BASE_PATH)
│   ├── io/                         ← Lua ↔ Python live channel (action / game_state)
│   ├── taught_models/              ← Human demos: run_N (recorded) / model_N (used by AI)
│   ├── ai_checkpoint/              ← AI's learned weights + pipeline state
│   ├── empirical_knowledge/        ← Knowledge built through play (types, moves, items, roster)
│   ├── debug/                      ← Ephemeral debug dumps
│   ├── logs/                       ← ai_logs/ + taught_logs/ (evaluation metrics)
│   └── log_analysis/               ← Generated comparison plots
├── agent/                          ← AI agent (autonomous player)
│   ├── trial6.ipynb                ← Agent notebook (6 cells)
│   ├── pokemon_bridge5.lua         ← Lua bridge for AI mode
│   ├── testing/reset.py            ← Resets AI-side JSONs for a fresh run
│   ├── log_analysis/analysis.ipynb ← Evaluation / comparison plots
│   ├── older_versions/             ← Earlier bridges + notebooks (reference)
│   └── models_tested/              ← Archived checkpoints from past runs
├── teaching/                       ← Human demonstration recorder
│   ├── poke_trial_learning_v4.ipynb ← Teaching notebook
│   ├── new_bridge_v4.lua            ← Lua bridge for teaching mode
│   ├── testing/reset.py             ← Resets teaching-side JSONs
│   └── OLD_CODE/                    ← Earlier teaching bridges/notebooks (reference)
├── game_files/                     ← Pokémon FireRed ROM + save (single copy)
└── docs/                           ← Final paper + project proposal
```

**Data flows one way:** `teaching/` → `agent/`. You record human demonstrations with the teaching notebook (which writes `jsons/taught_models/run_N/`), then rename each `run_N` to `model_N` so the AI agent loads it (the agent only reads `model_*` folders).

---

## Prerequisites

- **BizHawk Emulator** — download from [https://tasvideos.org/BizHawk](https://tasvideos.org/BizHawk). Extract the zip, no installer needed. Requires .NET 6.0 Desktop Runtime (BizHawk will prompt if missing). Select **mGBA** as the GBA core if asked.
- **Python 3.10+** with Jupyter Notebook support
- **Python packages:** `numpy` (everything else is standard library)
- **Pokémon FireRed (USA) ROM** — included at `game_files/Pokemon - FireRed Version (USA).gba`

---

## Before You Start: BizHawk Setup

These steps apply to both pipelines.

1. **Launch BizHawk** — run `EmuHawk.exe` from the extracted folder
2. **Load the ROM** — File → Open ROM → select `game_files/Pokemon - FireRed Version (USA).gba`
3. **Play manually to the overworld** — use keyboard controls to get past any title/intro screens until your character is standing in the game world:
   - Arrow keys = D-pad
   - Z = A button
   - X = B button
   - Enter = Start
   - Backspace = Select
   - (Configurable in Config → Controllers)
4. **Save in-game** (Start → Save) so you have a starting point

---

## Step 1: Record Human Demonstrations

> **Folder:** `teaching/`

You must record at least one human playthrough before the AI can run. Three runs are recommended for robust results.

1. Open BizHawk with the ROM loaded (game in overworld)
2. Open Lua console: **Tools → Lua Console**
3. Load `teaching/new_bridge_v4.lua` — the console should print memory addresses confirming the bridge is active
4. Open `teaching/poke_trial_learning_v4.ipynb` in Jupyter and run all cells sequentially
5. **Play the game normally in BizHawk.** Everything is recorded automatically — overworld movement, battles, menu navigation, bag usage, map transitions
6. Play as far as you want. More gameplay = better AI demonstrations.
7. `Ctrl+C` in the notebook to stop. All data saves to `jsons/taught_models/run_N/`
8. **Repeat for additional runs** — restart the game, run the notebook again. It auto-increments to `run_1`, `run_2`, etc.

**What gets recorded per run** (8 files in `jsons/taught_models/run_N/`):

| File | Contents |
|------|----------|
| `taught_model_checkpoint.json` | Perceptron weights and pipeline state |
| `taught_transitions.json` | Overworld Markov transitions (state → action) |
| `taught_battle_transitions.json` | Battle sequences with move/cursor data |
| `taught_bag_transitions.json` | Bag interaction frames |
| `taught_start_menu_transitions.json` | Start menu navigation frames |
| `taught_exploration_memory.json` | Spatial memory of visited tiles |
| `taught_nav_targets.json` | Ordered navigation waypoints from your path |
| `event_timeline.json` | Timeline of battles, level-ups, map changes |

---

## Step 2: Make Teaching Data Loadable by the AI

The teaching notebook saves runs as `run_N`, but the AI agent only loads folders named `model_N`. Both live in the same `jsons/taught_models/` directory, so you just rename (or copy) each run:

```
jsons/taught_models/run_0/   →   jsons/taught_models/model_1/
jsons/taught_models/run_1/   →   jsons/taught_models/model_2/
jsons/taught_models/run_2/   →   jsons/taught_models/model_3/
```

On Windows (PowerShell), copy each run to its model name:
```powershell
Copy-Item -Recurse -Force jsons\taught_models\run_0 jsons\taught_models\model_1
Copy-Item -Recurse -Force jsons\taught_models\run_1 jsons\taught_models\model_2
Copy-Item -Recurse -Force jsons\taught_models\run_2 jsons\taught_models\model_3
```

> This repo already ships with `model_1`–`model_3` prepared, so you can run the AI immediately without recording your own demonstrations first.

---

## Step 3: Run the AI Agent

> **Folder:** `agent/`

1. (Optional) Reset all AI-side files for a clean run:
   ```
   cd agent/testing
   python reset.py
   ```
   This clears the AI's checkpoint, exploration memory, and eval logs (all under `jsons/`). It does **not** touch your teaching data in `taught_models/`.

2. Open BizHawk with the ROM loaded (game in overworld, same starting point as your teaching runs)
3. Open Lua console: **Tools → Lua Console**
4. Load `agent/pokemon_bridge5.lua` — console should print `SB1=... SB2_key=... Badges=...`
5. Open `agent/trial6.ipynb` in Jupyter and run all 6 cells sequentially:

   | Cell | Contents |
   |------|----------|
   | 1 | Imports, constants, directory paths, activation library |
   | 2 | Perceptron class, Pipeline/Pool system, BattleBackprop |
   | 3 | Brain class (6 parts) — state management, knowledge, learning, evaluation |
   | 4 | Action selection — Markov matching, curiosity, battle/bag/menu routing |
   | 5 | Cache system, IOThread, SaveWorker, EventRecorder |
   | 6 | Main loop — creates Brain, loads models, starts threads, plays the game |

6. Cell 6 starts the main loop. The AI plays autonomously. Logs print every 100 steps, milestones every 500 steps.
7. `Ctrl+C` to stop. The agent saves all state and can resume where it left off.

---

## Step 4: Evaluate Results

After the AI has run, evaluation data is in:

- `jsons/logs/ai_logs/checkpoint_metrics.json` — AI performance at each map milestone
- `jsons/logs/ai_logs/stagnation_metrics.json` — AI stagnation intervals (7 types)
- `jsons/logs/taught_logs/` — Aggregated human metrics for comparison

The analysis notebook at `agent/log_analysis/analysis.ipynb` reads these logs and produces comparison plots (frames per checkpoint, cumulative progression, HP management, stagnation breakdown, efficiency table) and a summary report. Generated plots are written to `jsons/log_analysis/`.

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                  BizHawk Emulator                    │
│  ┌───────────────────────────────────────────────┐  │
│  │  Lua Script                                   │  │
│  │  • Reads GBA memory each frame                │  │
│  │  • Writes game_state.json                     │  │
│  │  • Reads action.json → presses button         │  │
│  └──────────────┬──────────────▲─────────────────┘  │
└─────────────────┼──────────────┼────────────────────┘
                  │              │
                  ▼              │
┌─────────────────────────────────────────────────────┐
│             Python Agent (trial6.ipynb)              │
│                                                     │
│  IOThread → CacheManager → Brain → Action Writer    │
│                                                     │
│  Decision priority chain:                           │
│  PartyMenu → Dialogue → StartMenu → Bag →          │
│  Battle → Preparation → Overworld                   │
│                                                     │
│  Decision sources:                                  │
│  1. Markov matching vs taught demonstrations        │
│  2. Pipeline perceptron scoring                     │
│  3. Curiosity-driven exploration (fallback)         │
└─────────────────────────────────────────────────────┘
```

**Multi-context pipelines:**
- **Overworld** (7 layers) — spatial awareness → area classification → frontier detection → objective management → pathfinding → execution → outcome observation
- **Battle** (6 layers) — identification → threat assessment → stay-or-bail → action selection → execution → outcome observation
- **Bag** (3 layers) — inventory awareness → item selection → execution
- **Party** (2 layers) — assessment → execution

**Knowledge systems:** move database, empirical type chart, item categorization, spatial memory, roster tracking, map battle stats, revenge targets — all persist across sessions via JSON.

---

## Key Design Principles

- **No reward shaping** — progress emerges from demonstration structure and curiosity
- **No deep learning** — single-layer perceptrons in hierarchical pipelines, fully interpretable
- **Empirical discovery** — type effectiveness, activation functions, spatial connectivity learned from experience
- **Structured memory reads** — game state from GBA memory addresses, not pixel processing
- **Persistent learning** — all knowledge accumulates across sessions via JSON storage
- **Demonstration-guided, not demonstration-dependent** — human demos are a strong prior, curiosity handles the rest

---

## Branches

- **`main`** — the canonical, streamlined codebase described above.
- **`modular`** — an experimental refactor of the agent into ~15 standalone Python modules (`brain_core.py`, `markov.py`, `perceptron.py`, `pool.py`, `navigation.py`, …) instead of a single notebook. Kept for reference.

---

## Authors

- **Angshuman Basu**
- **Nathaniel Maw**
- **Achal Mukkapati**

Khoury College of Computer Sciences, Northeastern University