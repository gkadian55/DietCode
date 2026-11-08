# DietCode 🚀

> **Inspectable DAG-based canvas that forecasts multi-LLM resource metrics, enables human-in-the-loop steering, and benchmarks real-time tokenomics for coding agents.**

DietCode is a local desktop application built with **Electron + React Flow (@xyflow/react) + Python ML Engine**. It runs **100% offline with self-trained models**—zero external API calls required.

---

## Key Features

1. **Self-Trained Local ML Regressors (Offline / No APIs)**:
   - **Feature Extractor**: Analyzes syntactic density, cognitive complexity, code keywords, and DAG depth.
   - **Gradient-Boosted Multi-Output Regressor**: Predicts input tokens, output tokens, and execution latency in **<2ms** per node.
   - **Pareto Efficiency Router**: Matches each subtask to the optimal agent (**ChatGPT / GPT-4o**, **Claude 3.5 Sonnet**, **Gemini 2.0 Flash**, **Gemini 1.5 Pro**) based on complexity vs cost vs latency.

2. **Inspectable DAG Canvas**:
   - Interactive node graph rendered at 60fps via `@xyflow/react`.
   - Node cards display real-time token counters, estimated cost in dollars, latency, and recommended agent badges.
   - Live cycle-prevention and topological level positioning.

3. **Human-in-the-Loop (HITL) Steering**:
   - **Edit Prompts & Tasks**: Modifying any task description automatically re-runs the self-trained forecaster and updates downstream context tokens.
   - **Agent Override**: Manually override any AI-recommended agent with one click.
   - **Add / Remove Nodes**: Connect custom subtasks or branch out dependencies dynamically.

4. **Multi-LLM Tokenomics Dashboard & Critical Path**:
   - Side-by-side comparative cards: Total cost across **All-GPT-4o**, **All-Claude-3.5**, **All-Gemini-2.0-Flash**, and **DietCode Pareto Routing**.
   - Calculates the **Critical Path** (the bottleneck chain of tasks that determines the overall sequential duration) and highlights affected nodes.

---

## Architecture Overview

```
DietCode/
├── electron/
│   ├── main.cjs               # Electron lifecycle, window controls & Python process manager
│   └── preload.cjs            # Secure IPC bridge
├── src/                       # React Frontend
│   ├── components/
│   │   ├── canvas/            # React Flow canvas & custom DAG nodes
│   │   ├── dashboard/         # Critical path banner & tokenomics matrix
│   │   ├── inspector/         # Node steering sidebar
│   │   ├── modal/             # Add subtask modal
│   │   └── header/            # Draggable header & goal input
│   ├── store/useDagStore.js   # Zustand state management
│   ├── App.jsx
│   └── index.css              # Custom glassmorphic design system
└── engine/                    # Local Python ML Engine
    ├── server.py              # FastAPI server (port 8765)
    ├── executor.py            # Async DAG execution and LiteLLM telemetry
    ├── models/
    │   ├── token_forecaster.py# Self-trained token & cost regressor
    │   └── planner.py         # Topological DAG decomposition & aggregates
    └── data/
        └── token_forecaster.pkl # Trained model weights
```

---

## How to Run

### Development Mode (Vite + Electron + Python)
```powershell
npm run dev
```

### Run Python Engine Standalone
```powershell
.\.venv\Scripts\python.exe engine\server.py
```

### Optional local Ollama routing
Install Ollama and a coding model before enabling local task execution:
```powershell
ollama serve
ollama pull qwen2.5-coder:7b
```

The executor routes routine tasks (tests, documentation, UI, and boilerplate)
to Ollama and keeps architecture, security, distributed-systems, and algorithm
tasks on Gemini by default. Configure this behavior in `.env`:
```env
GEMINI_API_KEY=your-gemini-api-key
DIETCODE_PRIMARY_MODEL=gemini-3-8-flash
DIETCODE_LOCAL_MODEL=ollama/qwen2.5-coder:7b
DIETCODE_LOCAL_ROUTING=true
OLLAMA_API_BASE=http://127.0.0.1:11434
```

Execution can also be selected in the dashboard:

- **Hybrid routing**: routine tasks use Ollama; complex tasks use the primary model.
- **Primary model only**: every task uses the selected primary model.
- **Ollama only**: every task stays local.

Parent outputs are compacted and duplicate context blocks are removed before
being sent to downstream tasks. The execution request supports a configurable
context character budget through `max_context_chars`.

### Build Production Bundle
```powershell
npm run build
```
