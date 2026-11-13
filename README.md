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

The dashboard also exposes per-run request timeout, retry count, and fallback
controls. Fallback can return a local simulation result when a provider is
unavailable; disabling it reports the provider failure instead.

Execution settings are available from the dashboard's **Execution settings**
panel. results are labeled **LIVE**, **SIMULATED**, or **BLOCKED**, provider failures include
a category such as quota, credentials, timeout, model availability, or Ollama
offline, and the tokenomics panel compares actual usage with the forecast.

## Neon PostgreSQL ledger

DietCode uses Neon-hosted PostgreSQL for the billing ledger. Add the connection
string from the Neon dashboard to the project `.env` file:

```env
DATABASE_URL=postgresql://user:password@ep-example.neon.tech/dietcode?sslmode=require
```

The application automatically uses the secure `psycopg` PostgreSQL driver. Do
not commit `.env` or expose the connection string.

The current schema is:

```text
users
  id, email, credit_balance, created_at

execution_logs
  id, user_id, task_name, model_used, input_tokens, output_tokens,
  cost_deducted, status, created_at
```

One user can have multiple execution logs. The `user_id` field on
`POST /api/execute` is optional so existing executions continue to work. When
provided, each task is recorded with its token usage, status, and measured
provider cost. Successful cloud-model tasks deduct their actual token cost
from the user's USD balance; Ollama tasks have zero provider cost.
The `cost_deducted` value in each execution log always matches the amount
actually deducted from the balance, including capped overrun settlements.

Before paid provider calls, DietCode forecasts the graph cost. If the estimate
exceeds the available balance, every task is returned with
`status: insufficient_funds`, no provider call is made, and the balance is
unchanged. The dashboard displays these tasks as **BLOCKED**. Failed provider
tasks do not incur a charge.

The estimate is reserved with an atomic database update before execution, so
concurrent requests cannot spend the same balance. Unused reserved funds are
refunded after measured usage is known. If actual usage exceeds the estimate,
DietCode charges only the reserved amount and reports a billing warning rather
than allowing the balance to become negative.

### Ledger API

Create a development user:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8765/api/users `
  -ContentType 'application/json' `
  -Body '{"email":"user@example.com","credit_balance":10.0}'
```

Read a balance:

```text
GET /api/users/{user_id}/balance
```

Read execution history:

```text
GET /api/users/{user_id}/executions
```

The current ledger has no authentication or live payment activation. Stripe
test checkout, signed webhooks, and idempotent top-ups are implemented; live
payment activation and production account verification remain future work.

### Stripe test payments

Stripe test checkout is available through `POST /api/billing/checkout`:

```json
{
  "user_id": 1,
  "amount_inr": 500
}
```

The endpoint creates a one-time INR Checkout session. With
`INR_PER_USD=100`, a ₹500 payment credits `$5.00`. The server stores the
conversion rate on the payment transaction.

Add these values to the local `.env` file:

```env
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
INR_PER_USD=100
```

Never expose or commit the secret key. To test crediting locally, install the
Stripe CLI, sign in, and forward test webhooks:

```powershell
stripe listen --forward-to http://127.0.0.1:8765/api/billing/stripe/webhook
```

Copy the `whsec_...` value printed by the CLI into `.env` as
`STRIPE_WEBHOOK_SECRET`, then restart the backend. Only a verified
`checkout.session.completed` event with `payment_status=paid` credits the
Neon balance. Duplicate webhook deliveries are ignored.

## VS Code integration

The initial VS Code extension is in `vscode-extension`. It provides commands
to send the current editor selection to the local execution engine and open the
DietCode dashboard. Set `dietcode.backendUrl` in VS Code when the backend is
running on a non-default address.

## Local Gemini simulator

Run `python simulator.py` to execute the bundled four-task DAG through one
Gemini model while preserving dependency ordering and parent-output context.
The simulator reads `GEMINI_API_KEY` from `.env` and ignores each task's
assigned model. Set `GEMINI_SIMULATOR_MODEL` or pass `--model` to select a
different Gemini model.

### Build Production Bundle
```powershell
npm run build
```
