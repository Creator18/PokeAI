# PokeAI — Curiosity-Driven Autonomous Game Agent for Pokémon FireRed

A hybrid autonomous agent that plays Pokémon FireRed (GBA) through demonstration-guided Markov transition matching, hierarchical multi-context perceptron pipelines, intrinsic curiosity-driven exploration, and persistent cross-session knowledge accumulation. The system operates via a Lua–Python bridge through the BizHawk emulator, reading structured game state directly from GBA memory — no reward shaping, no pixel-level deep learning, and fully interpretable at every decision layer.

**Authors:** Angshuman Basu, Nathaniel Maw, Achal Mukkapati  
**Affiliation:** Khoury College of Computer Sciences, Northeastern University

---

## Repository Structure

This repo is organized across four branches:

| Branch | Purpose |
|--------|---------|
| `master` (default) | AI agent code — the autonomous player |
| `teach_pokemon` | Human teaching/demonstration recording code |
| `modular` | Modularized `.py` codebase (final product, in progress) |
| `old-code` | Archived earlier iterations |

### `master` — AI Agent

| File | Description |
|------|-------------|
| `trial6.ipynb` | **Latest agent notebook** — full autonomous agent with all pipelines, Markov matching, curiosity, navigation, battle logic, and knowledge accumulation |
| `pokemon_bridge4.lua` | Lua bridge script that runs inside BizHawk, reads GBA memory each frame, and communicates game state to the Python agent via shared JSON files |
| `Pokemon - FireRed Version (USA).gba` | Game ROM |
| `Pokemon - FireRed Version (USA).sav` | Save file |
| Earlier `trial*.ipynb` files | Previous iterations of the agent notebook |

### `teach_pokemon` — Human Demonstration Recording

| File | Description |
|------|-------------|
| `poke_trial_learning_v4.ipynb` | Teaching notebook — used to record human gameplay demonstrations as Markov transition sequences that the agent learns from |
| `new_bridge_v4.lua` | Lua bridge for the teaching system |
| Game ROM, save files, BizHawk | Included for self-contained teaching setup |

---

## Prerequisites

- **BizHawk Emulator** — GBA-capable build ([https://tasvideos.org/BizHawk](https://tasvideos.org/BizHawk))
- **Python 3.10+** with Jupyter Notebook support
- **Python packages:** `numpy`, `json`, `os`, `time`, `threading`, `gc` (all standard library or common scientific stack)
- **Pokémon FireRed (USA) ROM** — included in repo

---

## How to Run

### Step 1: Set Up BizHawk

1. Download and install BizHawk.
2. Open BizHawk and load the ROM: **File → Open ROM → `Pokemon - FireRed Version (USA).gba`**
3. If a save file is present (`Pokemon - FireRed Version (USA).sav`), BizHawk will load it automatically from the same directory.

### Step 2: Load the Lua Bridge Script

1. In BizHawk, open the Lua console: **Tools → Lua Console**
2. In the Lua console, open the appropriate script:
   - For the **AI agent**: load `pokemon_bridge4.lua` (from `master`)
   - For **teaching/demonstration recording**: load `new_bridge_v4.lua` (from `teach_pokemon`)
3. The Lua script will begin reading GBA memory addresses each frame and writing structured game state (player position, map ID, battle status, HP, PP, inventory, party data, opponent data, badge flags, dialogue status) to a shared JSON file on disk.

### Step 3: Run the Python Notebook

#### To run the AI agent:
1. Switch to the `master` branch.
2. Open `trial6.ipynb` in Jupyter Notebook.
3. Run the cells sequentially. The notebook reads the game state JSON written by the Lua script, runs all decision-making logic (context detection, pipeline routing, Markov matching, curiosity, navigation, battle strategy), and writes an action JSON file that the Lua script reads to issue the corresponding button press in the emulator.
4. The agent will begin playing autonomously. Game state, knowledge bases, and spatial memory persist across sessions via JSON storage.

#### To record human demonstrations:
1. Switch to the `teach_pokemon` branch.
2. Open `poke_trial_learning_v4.ipynb` in Jupyter Notebook.
3. Run the cells to start the teaching system. Play the game manually in BizHawk — the notebook captures your (state, action) pairs as Markov transition sequences.
4. Recorded demonstrations are saved and can be loaded by the AI agent for Markov transition matching.

---

## How It Works

### Lua–Python Pipeline

The system runs as two communicating processes:
- The **Lua script** inside BizHawk extracts structured game state from GBA memory addresses every frame and writes it to a shared JSON file.
- The **Python agent** reads that file, makes decisions, and writes an action file that the Lua script reads to press the corresponding button.

This decouples perception from decision-making and keeps the emulator loop lightweight.

### Context Detection and Multi-Pipeline Architecture

The agent detects the current game context from memory flags and routes to the appropriate pipeline:
- **Overworld** — A* navigation, Markov-guided exploration, tile probing, curiosity fallback
- **Battle** — type-effectiveness reasoning, move selection, HP/PP tracking, revenge module
- **Bag** — inventory management through sequential menu navigation
- **Party** — Pokémon party operations, reordering, context-specific switching

Each pipeline has its own perceptron modules with independent weights.

### Demonstration Learning

Human demonstrations (recorded via the teaching notebook) are stored as Markov transition tables. During play, the agent matches its current state against the demonstration library, weighted by a transition authority score that grows with successful execution and decays with failures. When no match exceeds the authority threshold, the agent falls back to curiosity-driven exploration.

The Adaptive Checkpoint Window System scopes Markov matching to the agent's current game progress (badge count, map region, story flags), preventing cross-stage contamination.

### Knowledge Accumulation

The agent builds persistent knowledge across sessions: an empirically discovered type-effectiveness chart (via damage clustering, not a hardcoded table), a move database, item knowledge, spatial memory of visited tiles and discovered map connections, and badge progression tracking.

### Curiosity and Exploration

When demonstrations are unavailable, the agent explores via novelty scoring (favoring unvisited tiles/maps), transition bans (avoiding repeated failed actions), exploration debt (pressure to leave over-visited areas), and stagnation detection (forced exploration when stuck).

---

## Branch Workflow

```
teach_pokemon ──→ Record human demonstrations
       │
       ▼
    master ──→ AI agent uses demonstrations + curiosity to play autonomously
       │
       ▼
    modular ──→ Final modularized .py codebase (in progress)

    old-code ──→ Archived earlier iterations
```

---

## Key Design Principles

- **No reward shaping** — the agent has no score or fitness function; progress emerges from demonstration structure and curiosity
- **No deep learning** — all decision modules are single-layer perceptrons, chosen for full interpretability
- **Empirical discovery** — type effectiveness, activation functions, and spatial connectivity are learned from experience, not hardcoded
- **Structured memory reads** — game state comes from GBA memory addresses, not pixel processing, enabling real-time performance and richer features
- **Persistent learning** — knowledge accumulates across sessions via JSON storage

---

## Authors

- **Angshuman Basu**
- **Nathaniel Maw**
- **Achal Mukkapati**

Khoury College of Computer Sciences, Northeastern University | March 2026