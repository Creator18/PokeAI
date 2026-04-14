# PokeAI — Curiosity-Driven Autonomous Game Agent for Pokémon FireRed

A hybrid autonomous agent that plays Pokémon FireRed (GBA) through demonstration-guided Markov transition matching, hierarchical multi-context perceptron pipelines, intrinsic curiosity-driven exploration, and persistent cross-session knowledge accumulation. The system operates via a Lua–Python bridge through the BizHawk emulator, reading structured game state directly from GBA memory — no reward shaping, no pixel-level deep learning, and fully interpretable at every decision layer.

**Authors:** Angshuman Basu, Nathaniel Maw, Achal Mukkapati  
**Affiliation:** Khoury College of Computer Sciences, Northeastern University

---

## Table of Contents

1. [Repository Structure](#repository-structure)
2. [Prerequisites](#prerequisites)
3. [Setup Guide](#setup-guide)
4. [Running the Human Teaching Pipeline](#running-the-human-teaching-pipeline)
5. [Running the AI Agent](#running-the-ai-agent)
6. [System Architecture](#system-architecture)
7. [How the Two Branches Connect](#how-the-two-branches-connect)
8. [Directory Structure](#directory-structure)
9. [Key Design Principles](#key-design-principles)
10. [Evaluation](#evaluation)

---

## Repository Structure

This repo is organized across four branches:

| Branch | Purpose |
|--------|---------|
| `master` (default) | AI agent code — the autonomous player |
| `teach_pokemon` | Human teaching/demonstration recording code |
| `modular` | Modularized `.py` codebase (final product, in progress) |
| `old-code` | Archived earlier iterations |

The two branches you need to work with are **`master`** (AI agent) and **`teach_pokemon`** (human demonstration recording). The other two branches are for reference only.

### `master` — AI Agent

| File | Description |
|------|-------------|
| `trial6.ipynb` | **Latest agent notebook** — full autonomous agent (6 cells) with all pipelines, Markov matching, curiosity, navigation, battle logic, eval logging, and knowledge accumulation |
| `pokemon_bridge4.lua` | Lua bridge script v3.2.1 — runs inside BizHawk, reads GBA memory each frame, writes game state JSON, reads AI action JSON |
| `testing/reset.py` | Resets all JSON files to clean state for a fresh AI run |
| `Pokemon - FireRed Version (USA).gba` | Game ROM |
| `Pokemon - FireRed Version (USA).sav` | Save file |

### `teach_pokemon` — Human Demonstration Recording

| File | Description |
|------|-------------|
| `poke_trial_learning_v4.ipynb` | Teaching notebook — records human gameplay as Markov transition sequences, battle transitions, bag/menu transitions, navigation targets, and event timelines |
| `new_bridge_v4.lua` | Lua bridge for the teaching system — reads game memory AND records human button presses |
| Game ROM, save files | Included for self-contained teaching setup |

---

## Prerequisites

- **BizHawk Emulator** — GBA-capable build. Download from [https://tasvideos.org/BizHawk](https://tasvideos.org/BizHawk)
  - Windows: download the latest release, extract the zip, no installation needed
  - Requires .NET 6.0 Desktop Runtime (BizHawk will prompt you if missing)
- **Python 3.10+** with Jupyter Notebook support
- **Python packages:** `numpy` (the only non-standard-library dependency; everything else — `json`, `os`, `time`, `threading`, `gc`, `pathlib`, `collections` — is built in)
- **Pokémon FireRed (USA) ROM** — `Pokemon - FireRed Version (USA).gba` (included in repo)

---

## Setup Guide

### Step 1: Install BizHawk

1. Go to [https://tasvideos.org/BizHawk](https://tasvideos.org/BizHawk) and download the latest release for your platform.
2. Extract the zip to a folder (e.g., `C:\BizHawk\`). No installer — it runs from the extracted folder.
3. Run `EmuHawk.exe` to launch the emulator. If it asks for .NET runtime, follow the download link it provides, install it, and restart BizHawk.
4. On first launch, BizHawk may ask you to configure a GBA core. Select **mGBA** if prompted.

### Step 2: Load the Game ROM

1. In BizHawk: **File → Open ROM**
2. Navigate to the repo folder and select `Pokemon - FireRed Version (USA).gba`
3. The game will boot. If a `.sav` file exists in the same directory as the ROM, BizHawk loads it automatically.

### Step 3: Play Manually to the Starting Room

**This step is required before running either the teaching pipeline or the AI agent.** The Lua scripts and Python code expect the game to be past the title screen and inside the game world.

1. With the game loaded in BizHawk, use your keyboard to play:
   - **Arrow keys** = D-pad (Up/Down/Left/Right)
   - **Z** = A button
   - **X** = B button
   - **Enter** = Start
   - **Backspace** = Select
   - (These are BizHawk's default GBA key bindings. You can change them in **Config → Controllers**)
2. Start a new game or continue from a save. Play through any intro sequences until your character is standing in their **bedroom** (Player House 2F, Map 11) or anywhere in the overworld.
3. **Save the game in-game** (Start → Save) so you have a clean starting point.
4. You can also create a BizHawk **save state** (File → Save State → Slot 1) for quick reloading.

At this point the game is ready. Now you choose: record human demonstrations (teach_pokemon branch) or run the AI agent (master branch).

---

## Running the Human Teaching Pipeline

> **Branch:** `teach_pokemon`

The teaching pipeline records YOUR gameplay as structured demonstration data that the AI agent will later learn from. You need to do this **at least once** before the AI can run (it needs demonstrations to bootstrap from). We recommend **3 separate playthroughs** for robust averaging.

### Step 1: Switch to the Teaching Branch

```bash
git checkout teach_pokemon
```

### Step 2: Load the Teaching Lua Script

1. In BizHawk (with the game already loaded and past the title screen — see Step 3 above):
2. Open the Lua console: **Tools → Lua Console**
3. In the Lua console: **Script → Open Script** (or drag and drop)
4. Select `new_bridge_v4.lua` from the repo folder
5. The Lua console should print memory addresses and begin outputting frame data. This confirms the bridge is active.

### Step 3: Run the Teaching Notebook

1. Open `poke_trial_learning_v4.ipynb` in Jupyter Notebook
2. Run the cells **sequentially** (Cell 1 through Cell 6)
3. The notebook connects to the game via the shared JSON files that the Lua script is writing

### Step 4: Play the Game

Now just play Pokémon FireRed normally in BizHawk. Everything you do is being recorded:

- **Overworld movement** → stored as Markov transition sequences (state → action pairs)
- **Battles** → stored as battle transition sequences with move selections, outcomes, HP changes
- **Bag usage** → stored as bag interaction sequences
- **Menu navigation** → stored as start menu transition sequences
- **Map transitions** → stored as navigation targets with spatial coordinates
- **Events** → stored in an event timeline (battles, level-ups, map changes)

Play as far as you want. The more you play, the more demonstration data the AI has to learn from.

### Step 5: Stop and Save

1. Press `Ctrl+C` in the Jupyter notebook cell to stop the recording loop
2. The notebook will perform a final save of all demonstration data
3. All data is written to `jsons/taught_models/model_N/` where N is the run number

### Step 6: Repeat for Additional Runs

For better AI performance, record multiple playthroughs:

1. Reset the game to your starting save state
2. Run the teaching notebook again — it will auto-increment to the next model folder (`model_2`, `model_3`, etc.)
3. Play through again, ideally making slightly different choices to give the AI diverse demonstrations

**Output files per teaching run** (in `jsons/taught_models/model_N/`):

| File | Contents |
|------|----------|
| `taught_model_checkpoint.json` | Perceptron weights, pipeline state, all learned parameters |
| `taught_transitions.json` | Overworld Markov transitions (state, action, position, map) |
| `taught_battle_transitions.json` | Battle frame sequences with move/cursor data |
| `taught_bag_transitions.json` | Bag interaction frames |
| `taught_start_menu_transitions.json` | Start menu navigation frames |
| `taught_exploration_memory.json` | Spatial memory of visited tiles and discovered transitions |
| `taught_nav_targets.json` | Ordered navigation waypoints extracted from your path |
| `event_timeline.json` | Timeline of battles, level-ups, map transitions, preparation points |

---

## Running the AI Agent

> **Branch:** `master`

The AI agent reads the demonstration data you recorded, bootstraps its perceptron weights from the best teaching checkpoint, and then plays autonomously.

### Step 1: Switch to the Master Branch

```bash
git checkout master
```

### Step 2: Ensure Demonstration Data Exists

The AI needs taught models to bootstrap from. Check that `jsons/taught_models/` contains at least one `model_N/` folder with populated JSON files from the teaching pipeline.

If starting completely fresh, run the reset script first:

```bash
cd testing
python reset.py
```

This creates the full directory structure and resets all AI-side files to empty templates. It does **not** touch your teaching data in `taught_models/`.

### Step 3: Load the AI Lua Script

1. In BizHawk (game loaded, past title screen, character in the overworld):
2. Open Lua console: **Tools → Lua Console**
3. Load `pokemon_bridge4.lua`
4. The console should print memory addresses and `SB1=... SB2_key=... Badges=...` confirming the bridge is active

### Step 4: Run the AI Agent Notebook

1. Open `trial6.ipynb` in Jupyter Notebook
2. Run the cells **sequentially** (Cell 1 through Cell 6):
   - **Cell 1:** Imports, constants, directory paths, activation library
   - **Cell 2:** Perceptron class, Pipeline/Pool system, BattleBackprop
   - **Cell 3:** Brain class (Parts 1-6) — all state management, knowledge, learning, evaluation
   - **Cell 4:** Action selection (anticipatory_action, Markov matching, curiosity scoring, battle/bag/menu routing)
   - **Cell 5:** Cache system, IOThread, SaveWorker, EventRecorder, state building functions
   - **Cell 6:** Main loop — creates the Brain, loads models, starts threads, runs the game loop

3. Cell 6 starts the main loop. The AI will begin playing immediately.

### Step 5: Watch and Monitor

The notebook prints detailed logs every 100 steps and milestone reports every 500 steps, showing:

- Current map, position, game state
- Markov matching rate, battle outcomes, stagnation status
- Pipeline authority, perceptron counts, knowledge accumulation
- Evaluation checkpoints and stagnation snapshots
- Navigation status, window bounds, efficiency metrics

### Step 6: Stop the Agent

Press `Ctrl+C` in the notebook. The agent will:
1. Stop all background threads (IO, save worker, event recorder)
2. Force-close any active stagnation snapshots
3. Perform a final synchronous save of all state
4. Save evaluation logs (checkpoint_metrics.json, stagnation_metrics.json)
5. Print final statistics

All progress is persistent — restart the notebook and it resumes from where it left off.

---

## System Architecture

### Lua–Python Bridge

```
┌─────────────────────────────────────────────────────────┐
│                    BizHawk Emulator                      │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Pokémon FireRed GBA ROM                         │   │
│  │  ┌────────────────────────────────────────────┐  │   │
│  │  │  Lua Script (pokemon_bridge4.lua)          │  │   │
│  │  │  • Reads GBA memory addresses each frame   │  │   │
│  │  │  • Writes game_state.json (position, map,  │  │   │
│  │  │    battle data, party, bag, menu, badges)   │  │   │
│  │  │  • Reads action.json and presses button     │  │   │
│  │  └──────────────┬──────────────▲───────────────┘  │   │
│  └─────────────────┼──────────────┼──────────────────┘   │
└────────────────────┼──────────────┼──────────────────────┘
                     │ game_state   │ action.json
                     │   .json      │
                     ▼              │
┌────────────────────────────────────────────────────────┐
│               Python Agent (trial6.ipynb)              │
│                                                        │
│  IOThread ──→ CacheManager ──→ Brain ──→ Action        │
│  (reads        (parses          (decides)   (writes    │
│   state)        state)                       action)   │
│                                                        │
│  Priority Chain:                                       │
│  PartyMenu → Dialogue → StartMenu → Bag →             │
│  Battle → Preparation → Overworld                      │
│                                                        │
│  Decision Sources:                                     │
│  1. Markov matching vs taught demonstrations           │
│  2. Pipeline perceptron scoring                        │
│  3. Curiosity-driven exploration (fallback)            │
└────────────────────────────────────────────────────────┘
```

### Context Detection and Multi-Pipeline Architecture

The agent detects the current game context from memory flags and routes to the appropriate decision pipeline:

- **Overworld** — Markov matching against taught transitions, A* navigation to taught targets, tile probing, curiosity fallback. 7-layer pipeline: spatial awareness → area classification → frontier detection → objective management → pathfinding → execution → outcome observation.
- **Battle** — Move scoring (pipeline + direct knowledge + type effectiveness + damage clustering), cursor navigation, HP/PP tracking, run logic, forced switching, revenge module. 6-layer pipeline: identification → threat assessment → stay-or-bail → action selection → execution → outcome observation.
- **Bag** — Markov-guided menu navigation, item observation and categorization, healing/catching item awareness. 3-layer pipeline.
- **Party** — Context-aware Pokémon switching (voluntary and forced), party assessment. 2-layer pipeline.
- **Start Menu** — Markov-guided menu navigation for preparation sequences (heal at Pokémon Center, manage party).
- **Dialogue** — Text skipping (A/B) for pure text, Markov-guided choice selection for dialogue choices.

### Demonstration Learning

Human demonstrations (from `teach_pokemon` branch) are stored as Markov transition tables. During play, the agent matches its current state (position, map, direction, game state flags) against the demonstration library. When the match score exceeds a threshold, the agent executes the demonstrated action. When no match is found, it falls back to curiosity-driven exploration.

The **Adaptive Checkpoint Window** system scopes Markov matching to the agent's current game progress (badge count, level, map region), preventing the agent from matching against demonstrations from later in the game.

### Knowledge Accumulation

The agent builds persistent knowledge across sessions:

- **Move knowledge** — Per-move, per-species damage averages, miss rates, status effects (empirically discovered through battles, not hardcoded)
- **Type effectiveness** — Discovered via damage clustering (Track A) or loaded from a ground truth file (Track B)
- **Item knowledge** — Items categorized by observed effects (heal_hp, heal_status, catch) through use
- **Spatial memory** — Visited tiles, discovered map transitions, tile interaction outcomes
- **Roster** — Party Pokémon species, moves, stats tracked across battles
- **Map battle stats** — Per-map encounter rates, average HP cost, enemy levels
- **Revenge targets** — Locations where the AI lost, with grinding targets to return stronger

### Evaluation System (v17.8.1)

The AI logs its own performance metrics in a format compatible with human demonstration aggregation:

- **Checkpoint metrics** — Triggered on: first visit to a new map, trainer battle completion, badge acquisition. Records timestep, frames since last checkpoint, team level, party HP ratio, badge count.
- **Stagnation metrics** — 7 detection types (position_stuck, action_pattern, action_repeat, area_grinding, no_level_progress, no_map_progress, backtracking) tracked as open/close intervals with duration and resolution.

These logs enable direct quantitative comparison between AI and human performance.

---

## How the Two Branches Connect

```
┌──────────────────────────────────────────────────────────┐
│  teach_pokemon branch                                     │
│                                                           │
│  Human plays Pokémon FireRed manually                     │
│         │                                                 │
│         ▼                                                 │
│  Teaching notebook records:                               │
│  • Overworld transitions (state → action)                 │
│  • Battle transitions (cursor → move selections)          │
│  • Bag/menu transitions                                   │
│  • Navigation targets (ordered waypoints)                 │
│  • Event timeline (battles, level-ups, map changes)       │
│  • Model checkpoint (perceptron weights)                  │
│         │                                                 │
│         ▼                                                 │
│  Saved to: jsons/taught_models/model_N/                   │
│  (8 JSON files per teaching run)                          │
└──────────────────────┬───────────────────────────────────┘
                       │
                       │  Teaching data is read-only input
                       │  to the AI agent
                       ▼
┌──────────────────────────────────────────────────────────┐
│  master branch                                            │
│                                                           │
│  AI agent loads all taught_models/model_N/ folders        │
│  Merges demonstration data from all teaching runs         │
│  Bootstraps perceptron weights from best checkpoint       │
│         │                                                 │
│         ▼                                                 │
│  AI plays autonomously:                                   │
│  • Markov matches against taught transitions              │
│  • Falls back to curiosity when no match                  │
│  • Learns from state-change novelty                       │
│  • Builds empirical knowledge through play                │
│  • Logs evaluation metrics for comparison                 │
│         │                                                 │
│         ▼                                                 │
│  AI state saved to: jsons/ai_checkpoint/                  │
│  Knowledge saved to: jsons/empirical_knowledge/           │
│  Eval logs saved to: jsons/logs/ai_logs/                  │
└──────────────────────────────────────────────────────────┘
```

The teaching data flows **one way**: from `teach_pokemon` → `master`. The AI agent never writes to the teaching data. Multiple teaching runs provide richer demonstrations and more robust Markov matching.

---

## Directory Structure

Both branches share the same `jsons/` directory structure:

```
cogai/
├── jsons/
│   ├── io/                           # Real-time Lua ↔ Python communication
│   │   ├── action.json               #   Python writes, Lua reads (button press)
│   │   └── game_state.json           #   Lua writes, Python reads (full game state)
│   │
│   ├── taught_models/                # Human demonstration data (from teach_pokemon)
│   │   ├── model_1/                  #   First teaching run
│   │   │   ├── taught_model_checkpoint.json
│   │   │   ├── taught_transitions.json
│   │   │   ├── taught_battle_transitions.json
│   │   │   ├── taught_bag_transitions.json
│   │   │   ├── taught_start_menu_transitions.json
│   │   │   ├── taught_exploration_memory.json
│   │   │   ├── taught_nav_targets.json
│   │   │   └── event_timeline.json
│   │   ├── model_2/                  #   Second teaching run
│   │   └── model_3/                  #   Third teaching run (etc.)
│   │
│   ├── ai_checkpoint/                # AI's own learned state (master branch)
│   │   ├── model_checkpoint.json     #   Full brain state, pipeline weights, eval state
│   │   └── residual_perceptrons.json #   Paged-out perceptrons from pipeline pools
│   │
│   ├── empirical_knowledge/          # Knowledge built through AI play
│   │   ├── exploration_memory.json   #   Visited tiles, transitions per map
│   │   ├── roster.json               #   Party Pokémon species/moves
│   │   ├── move_knowledge.json       #   Per-move damage/accuracy vs species
│   │   ├── item_knowledge.json       #   Item categorization from use
│   │   ├── type_clusters.json        #   Empirical type chart (Track A)
│   │   ├── type_data.json            #   Ground truth types (Track B, optional)
│   │   └── ai_event_timeline.json    #   AI's event history
│   │
│   ├── debug/                        # Adaptive window debug dumps
│   │   ├── active_transitions.json
│   │   ├── active_battle.json
│   │   ├── active_bag.json
│   │   └── active_start_menu.json
│   │
│   └── logs/                         # Evaluation metrics
│       ├── ai_logs/                  #   AI agent performance
│       │   ├── checkpoint_metrics.json
│       │   └── stagnation_metrics.json
│       └── taught_logs/              #   Human performance (aggregated)
│           ├── aggregated_checkpoint_metrics.json
│           └── aggregated_stagnation_metrics.json
│
├── testing/
│   └── reset.py                      # Resets all JSON files for fresh run
│
├── trial6.ipynb                      # AI agent notebook (master)
├── pokemon_bridge4.lua               # AI Lua bridge (master)
├── Pokemon - FireRed Version (USA).gba
└── Pokemon - FireRed Version (USA).sav
```

---

## Key Design Principles

- **No reward shaping** — the agent has no score or fitness function. Progress emerges from demonstration structure and curiosity-driven exploration of state-change novelty.
- **No deep learning** — all decision modules are single-layer perceptrons organized in hierarchical pipelines, chosen for full interpretability at every decision layer.
- **Empirical discovery** — type effectiveness, move power, activation functions, and spatial connectivity are learned from experience, not hardcoded.
- **Structured memory reads** — game state comes from GBA memory addresses (not pixel processing), enabling real-time performance and richer feature extraction.
- **Persistent learning** — all knowledge (exploration memory, move database, item knowledge, type chart, pipeline weights) accumulates across sessions via JSON storage.
- **Demonstration-guided, not demonstration-dependent** — the AI uses human demonstrations as a strong prior but can explore autonomously when demonstrations are unavailable or insufficient.

---

## Evaluation

The system includes a built-in evaluation framework that enables direct quantitative comparison between AI and human performance:

- **Checkpoint metrics** compare frames-to-reach, team level, and party HP at each map milestone
- **Stagnation metrics** track time spent stuck, backtracking, or repeating actions (7 detection types for AI, 4 for human)
- **Battle metrics** track win/loss/run rates, move selection quality, and HP management

An analysis notebook (`jsons/log_analysis/analysis.ipynb`) produces comparison plots and a summary report. See the `jsons/logs/` directory for raw evaluation data.

---

## Authors

- **Angshuman Basu**
- **Nathaniel Maw**
- **Achal Mukkapati**

Khoury College of Computer Sciences, Northeastern University