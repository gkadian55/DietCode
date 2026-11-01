import re
from typing import Any

import networkx as nx

try:
    from .token_forecaster import TokenForecaster
except ImportError:
    from token_forecaster import TokenForecaster


class DAGPlanner:
    def __init__(self, forecaster: TokenForecaster):
        self.forecaster = forecaster

    def decompose_goal(self, goal: str) -> dict[str, Any]:
        """Decomposes a project goal into a structured DAG with forecasted tokenomics and agent allocation."""
        raw_tasks = self._generate_subtasks(goal)

        # Build networkx graph to calculate depth and dependencies
        g = nx.DiGraph()
        for t in raw_tasks:
            g.add_node(t["id"])

        edges = []
        for t in raw_tasks:
            for dep_id in t.get("dependencies", []):
                if g.has_node(dep_id):
                    g.add_edge(dep_id, t["id"])
                    edges.append({
                        "id": f"e_{dep_id}_{t['id']}",
                        "source": dep_id,
                        "target": t["id"],
                        "animated": True,
                        "style": {"stroke": "#64748b", "strokeWidth": 2}
                    })

        # Cycle safety check
        if not nx.is_directed_acyclic_graph(g):
            cycles = list(nx.simple_cycles(g))
            for cycle in cycles:
                if len(cycle) >= 2:
                    g.remove_edge(cycle[-1], cycle[0])
                    edges = [e for e in edges if not (e["source"] == cycle[-1] and e["target"] == cycle[0])]

        # Assign hierarchical DAG levels for 2D canvas layout
        topo_order = list(nx.topological_sort(g))
        levels = {}
        for node_id in topo_order:
            preds = list(g.predecessors(node_id))
            if not preds:
                levels[node_id] = 0
            else:
                levels[node_id] = max(levels[p] for p in preds) + 1

        # Calculate position coordinates (X: horizontal rank, Y: vertical spread)
        level_groups: dict[int, list[str]] = {}
        for node_id, lvl in levels.items():
            level_groups.setdefault(lvl, []).append(node_id)

        positions = {}
        x_gap = 360
        y_gap = 180

        for lvl, n_ids in level_groups.items():
            total_h = (len(n_ids) - 1) * y_gap
            for idx, n_id in enumerate(n_ids):
                x = 80 + lvl * x_gap
                y = 120 + (idx * y_gap) - (total_h / 4)
                positions[n_id] = {"x": round(x), "y": round(y)}

        # Run token forecaster on each node
        processed_nodes = []
        for t in raw_tasks:
            nid = t["id"]
            upstream_count = len(list(g.predecessors(nid)))
            depth = levels.get(nid, 1) + 1

            forecast = self.forecaster.forecast_node(
                title=t["title"],
                description=t["description"],
                upstream_count=upstream_count,
                depth=depth,
                category=t.get("category", "")
            )

            processed_nodes.append({
                "id": nid,
                "type": "agentNode",
                "position": positions.get(nid, {"x": 100, "y": 100}),
                "data": {
                    "id": nid,
                    "title": t["title"],
                    "description": t["description"],
                    "category": t["category"],
                    "status": "pending",
                    "dependencies": t.get("dependencies", []),
                    "predictedTokens": forecast["predictedTokens"],
                    "complexityScore": forecast["complexityScore"],
                    "recommendedAgent": forecast["recommendedAgent"],
                    "assignedAgent": forecast["recommendedAgent"]["id"],
                    "modelEvaluations": forecast["modelEvaluations"]
                }
            })

        aggregates = self.calculate_graph_aggregates(processed_nodes, g)

        return {
            "goal": goal,
            "nodes": processed_nodes,
            "edges": edges,
            "aggregates": aggregates
        }

    def _generate_subtasks(self, goal: str) -> list[dict[str, Any]]:
        """Decomposes goals adaptively into 1, 2, 4, or N steps based on true task complexity."""
        clean_goal = goal.strip()
        lower_goal = clean_goal.lower()
        words = set(re.findall(r"\b\w+\b", lower_goal))
        word_count = len(clean_goal.split())

        def match_intent(keywords: list[str]) -> bool:
            return any(kw in words or (len(kw) > 3 and kw in lower_goal) for kw in keywords)

        # -------------------------------------------------------------------------
        # TIER 1: Trivial / Micro Tasks (Exactly 1 Focused Step)
        # e.g., "create a webpage with 'Hello World' only", "generate an image of a cat"
        # -------------------------------------------------------------------------
        is_micro_task = False
        if ("hello world" in lower_goal or "only" in words or "just" in words or "single" in words) and word_count <= 10:
            is_micro_task = True
        elif any(k in lower_goal for k in ["create an image", "generate an image", "make an image", "single page", "simple script", "regex for", "regex to", "function to", "write a function"]):
            is_micro_task = True
        elif word_count <= 4 and not any(w in words for w in ["app", "system", "fullstack", "platform", "service"]):
            is_micro_task = True

        if is_micro_task:
            if "image" in lower_goal:
                return [{
                    "id": "step-1-generate",
                    "title": "1. Generate Image Asset",
                    "description": f"Synthesize visual image asset according to prompt requirements: '{clean_goal}'.",
                    "category": "Asset Generation",
                    "dependencies": []
                }]
            elif "regex" in lower_goal:
                return [{
                    "id": "step-1-regex",
                    "title": "1. Implement & Validate Regex",
                    "description": f"Write regular expression pattern and verify against target test inputs: '{clean_goal}'.",
                    "category": "Utility",
                    "dependencies": []
                }]
            elif "hello world" in lower_goal or "webpage" in lower_goal or "html" in lower_goal:
                return [{
                    "id": "step-1-page",
                    "title": "1. Create 'Hello World' Webpage",
                    "description": "Build a clean single HTML page displaying 'Hello World' with centered responsive styling.",
                    "category": "Frontend",
                    "dependencies": []
                }]
            else:
                return [{
                    "id": "step-1-task",
                    "title": f"1. Execute: {clean_goal[:45]}",
                    "description": f"Directly implement the requested single-step task: '{clean_goal}'.",
                    "category": "Implementation",
                    "dependencies": []
                }]

        # -------------------------------------------------------------------------
        # TIER 2: Small / 2-Step Tasks (Exactly 2 Steps)
        # e.g., "simple counter button in react", "weather script fetching from api"
        # -------------------------------------------------------------------------
        is_small_task = (
            word_count <= 8 
            and not any(w in words for w in ["fullstack", "enterprise", "system", "architecture", "distributed", "platform", "microservice", "multi"])
        )
        if is_small_task:
            if match_intent(["react", "button", "counter", "form", "toggle", "component", "modal", "ui", "widget"]):
                return [
                    {
                        "id": "step-1-component",
                        "title": "1. Build Component Layout & State",
                        "description": f"Create the component structure, define local state, and apply styles for {clean_goal}.",
                        "category": "Frontend",
                        "dependencies": []
                    },
                    {
                        "id": "step-2-interaction",
                        "title": "2. Event Handling & Behavior",
                        "description": "Wire up user click events, state transitions, and validation feedback.",
                        "category": "Frontend",
                        "dependencies": ["step-1-component"]
                    }
                ]
            elif match_intent(["script", "fetch", "api", "scrape", "cli", "utility"]):
                return [
                    {
                        "id": "step-1-fetch",
                        "title": "1. Core Logic & API Request",
                        "description": f"Implement request handling, data fetching, and response parsing for {clean_goal}.",
                        "category": "Backend",
                        "dependencies": []
                    },
                    {
                        "id": "step-2-output",
                        "title": "2. Formatting & Error Handling",
                        "description": "Format output presentation, add input validation, and handle error scenarios gracefully.",
                        "category": "QA & Testing",
                        "dependencies": ["step-1-fetch"]
                    }
                ]

        # -------------------------------------------------------------------------
        # TIER 4: Enterprise Complex Multi-Service Architecture (5 to 7 Steps)
        # Triggered when multiple distributed/enterprise subsystems are explicitly specified
        # -------------------------------------------------------------------------
        complex_signals = ["distributed", "microservice", "microservices", "kafka", "queue", "redis", "cache", "kubernetes", "k8s", "docker", "telemetry", "observability", "auth", "jwt", "database", "postgres", "sql"]
        signal_count = sum(1 for s in complex_signals if s in words or s in lower_goal)
        is_enterprise_complex = signal_count >= 3 or ("distributed" in words and any(w in words for w in ["multi", "system", "architecture"]))

        if is_enterprise_complex:
            tasks: list[dict[str, Any]] = [
                {
                    "id": "step-1-arch",
                    "title": "1. Enterprise Architecture & Protocol Spec",
                    "description": f"Define system topology, service boundary contracts, and communication protocols for {clean_goal}.",
                    "category": "Architecture",
                    "dependencies": []
                },
                {
                    "id": "step-2-data",
                    "title": "2. Distributed Data Models & Migrations",
                    "description": "Formulate persistent data schemas, relational indexes, and automated transactional migrations.",
                    "category": "Architecture",
                    "dependencies": ["step-1-arch"]
                }
            ]

            has_auth = match_intent(["auth", "security", "jwt", "oauth", "rbac", "user", "session", "login"])
            has_queue = match_intent(["kafka", "queue", "stream", "pubsub", "event", "rabbitmq", "celery", "distributed"])
            has_ui = match_intent(["ui", "frontend", "dashboard", "react", "canvas", "web", "view"])

            prev_id = "step-2-data"
            if has_auth:
                tasks.append({
                    "id": "step-3-auth",
                    "title": "3. Authentication & RBAC Security",
                    "description": "Implement token signing, session rotation, security middleware, and role-based permissions.",
                    "category": "Architecture",
                    "dependencies": ["step-2-data"]
                })
                prev_id = "step-3-auth"

            if has_queue:
                tasks.append({
                    "id": "step-4-queue",
                    "title": f"{len(tasks) + 1}. Distributed Message Bus & Workers",
                    "description": "Deploy partitioned event streams, backpressure management, and asynchronous background workers.",
                    "category": "Backend",
                    "dependencies": [prev_id]
                })
                prev_id = "step-4-queue"

            tasks.append({
                "id": f"step-{len(tasks) + 1}-core",
                "title": f"{len(tasks) + 1}. Core Service Engine & APIs",
                "description": "Implement high-throughput business logic services, RPC/REST interfaces, and state evaluators.",
                "category": "Backend",
                "dependencies": [prev_id]
            })

            if has_ui:
                tasks.append({
                    "id": f"step-{len(tasks) + 1}-ui",
                    "title": f"{len(tasks) + 1}. Real-Time Management Dashboard",
                    "description": "Build responsive visual interface, telemetry widgets, and live WebSocket state synchronization.",
                    "category": "Frontend",
                    "dependencies": [tasks[-1]["id"]]
                })

            tasks.append({
                "id": f"step-{len(tasks) + 1}-qa",
                "title": f"{len(tasks) + 1}. End-to-End Stress & Resilience Testing",
                "description": "Run contract tests, load benchmarks, failure resilience checks, and end-to-end integration flows.",
                "category": "QA & Testing",
                "dependencies": [tasks[-1]["id"]]
            })
            return tasks

        # -------------------------------------------------------------------------
        # TIER 3: Standard Application Tasks (3 to 4 Clear Steps)
        # -------------------------------------------------------------------------
        is_ai_agent = match_intent(["agent", "llm", "ai", "model", "token", "prompt", "rag", "chat", "gpt", "gemini", "claude", "forecaster"])
        is_frontend = match_intent(["ui", "frontend", "dashboard", "react", "canvas", "web", "view", "interface", "client"])
        is_backend_only = match_intent(["api", "backend", "microservice", "service", "rest", "graphql", "server", "endpoint"]) and not is_frontend
        is_cli_or_script = match_intent(["cli", "script", "tool", "scraper", "scrape", "automation", "parser", "pipeline"]) and not (is_frontend or is_ai_agent)

        if is_ai_agent:
            return [
                {
                    "id": "step-1-spec",
                    "title": "1. System Design & Agent Roles",
                    "description": f"Define agent responsibilities, task routing rules, and data schemas for {clean_goal}.",
                    "category": "Architecture",
                    "dependencies": []
                },
                {
                    "id": "step-2-engine",
                    "title": "2. Agent Execution & Model Router",
                    "description": "Implement core agent orchestration logic, model routing, and token budget management.",
                    "category": "Backend",
                    "dependencies": ["step-1-spec"]
                },
                {
                    "id": "step-3-ui",
                    "title": "3. Interactive Canvas & Dashboard",
                    "description": "Build user controls to visualize the agent DAG, edit prompts, and inspect live token metrics.",
                    "category": "Frontend",
                    "dependencies": ["step-2-engine"]
                },
                {
                    "id": "step-4-qa",
                    "title": "4. Verification & Model Benchmarks",
                    "description": "Test multi-agent workflows, benchmark token costs, and verify error recovery handling.",
                    "category": "QA & Testing",
                    "dependencies": ["step-3-ui"]
                }
            ]
        elif is_cli_or_script:
            return [
                {
                    "id": "step-1-cli-spec",
                    "title": "1. CLI Commands & Config",
                    "description": f"Define command-line options, flag arguments, and configuration loading for {clean_goal}.",
                    "category": "Architecture",
                    "dependencies": []
                },
                {
                    "id": "step-2-processing",
                    "title": "2. Core Automation Logic",
                    "description": "Build data transformation, file handling, and core operational logic with progress feedback.",
                    "category": "Backend",
                    "dependencies": ["step-1-cli-spec"]
                },
                {
                    "id": "step-3-testing",
                    "title": "3. CLI Validation & Packaging",
                    "description": "Write integration test cases, verify exit codes, and package the utility for distribution.",
                    "category": "QA & Testing",
                    "dependencies": ["step-2-processing"]
                }
            ]
        elif is_backend_only:
            return [
                {
                    "id": "step-1-schema",
                    "title": "1. API Contract & Database Schema",
                    "description": f"Design endpoint specifications, request/response models, and database table schemas for {clean_goal}.",
                    "category": "Architecture",
                    "dependencies": []
                },
                {
                    "id": "step-2-services",
                    "title": "2. Service Handlers & Business Logic",
                    "description": "Implement database CRUD operations, business logic controllers, and service handlers.",
                    "category": "Backend",
                    "dependencies": ["step-1-schema"]
                },
                {
                    "id": "step-3-security",
                    "title": "3. Authentication & Middleware",
                    "description": "Add user authentication, input validation middleware, rate-limiting, and error handling.",
                    "category": "Architecture",
                    "dependencies": ["step-2-services"]
                },
                {
                    "id": "step-4-testing",
                    "title": "4. API Test Suite & Validation",
                    "description": "Write automated unit tests for all endpoints and verify database transactional integrity.",
                    "category": "QA & Testing",
                    "dependencies": ["step-3-security"]
                }
            ]
        else:
            return [
                {
                    "id": "step-1-architecture",
                    "title": "1. Architecture & Data Models",
                    "description": f"Define project structure, data entities, and component specifications for {clean_goal}.",
                    "category": "Architecture",
                    "dependencies": []
                },
                {
                    "id": "step-2-backend",
                    "title": "2. Core Backend & API Endpoints",
                    "description": "Implement server routes, data processing functions, and business logic handlers.",
                    "category": "Backend",
                    "dependencies": ["step-1-architecture"]
                },
                {
                    "id": "step-3-frontend",
                    "title": "3. Frontend UI & State Management",
                    "description": "Create user interface views, input forms, and connect them to backend API endpoints.",
                    "category": "Frontend",
                    "dependencies": ["step-2-backend"]
                },
                {
                    "id": "step-4-testing",
                    "title": "4. Integration Testing & Polish",
                    "description": "Verify end-to-end user workflows, test edge cases, and ensure clean error handling.",
                    "category": "QA & Testing",
                    "dependencies": ["step-3-frontend"]
                }
            ]

        return tasks

    def calculate_graph_aggregates(self, nodes: list[dict[str, Any]], g: nx.DiGraph | None = None) -> dict[str, Any]:
        """Calculates total tokenomics, comparative costs, latency, and critical path."""
        total_input_tokens = sum(n["data"]["predictedTokens"]["input"] for n in nodes)
        total_output_tokens = sum(n["data"]["predictedTokens"]["output"] for n in nodes)
        total_tokens = total_input_tokens + total_output_tokens

        graph = g
        if graph is None:
            graph = nx.DiGraph()
            for n in nodes:
                graph.add_node(n["id"])
            for n in nodes:
                for dep in n["data"].get("dependencies", []):
                    if graph.has_node(dep):
                        graph.add_edge(dep, n["id"])

        all_gpt4o_cost = sum(n["data"]["modelEvaluations"]["gpt-4o"]["totalCost"] for n in nodes)
        all_claude_cost = sum(n["data"]["modelEvaluations"]["claude-3-5-sonnet"]["totalCost"] for n in nodes)
        all_gemini_cost = sum(n["data"]["modelEvaluations"]["gemini-2-0-flash"]["totalCost"] for n in nodes)

        allocated_cost = 0.0
        agent_counts: dict[str, int] = {}
        for n in nodes:
            assigned_id = n["data"].get("assignedAgent", n["data"]["recommendedAgent"]["id"])
            agent_counts[assigned_id] = agent_counts.get(assigned_id, 0) + 1
            if assigned_id in n["data"]["modelEvaluations"]:
                allocated_cost += n["data"]["modelEvaluations"][assigned_id]["totalCost"]
            else:
                allocated_cost += n["data"]["recommendedAgent"]["estimatedCost"]

        latency_map = {
            n["id"]: n["data"]["modelEvaluations"][n["data"].get("assignedAgent", "gpt-4o")]["latencySec"]
            for n in nodes
        }

        critical_path = []
        critical_path_latency = 0.0
        if nx.is_directed_acyclic_graph(graph) and len(graph) > 0:
            try:
                topo = list(nx.topological_sort(graph))
                dist = {v: latency_map.get(v, 0.0) for v in topo}
                parent = {v: None for v in topo}
                for u in topo:
                    for v in graph.successors(u):
                        w = latency_map.get(v, 0.0)
                        if dist[u] + w > dist[v]:
                            dist[v] = dist[u] + w
                            parent[v] = u

                if dist:
                    max_node = max(dist, key=dist.get)
                    critical_path_latency = round(dist[max_node], 2)
                    curr = max_node
                    while curr is not None:
                        critical_path.append(curr)
                        curr = parent[curr]
                    critical_path.reverse()
            except nx.NetworkXError as err:
                print(f"[Planner] Critical path calculation note: {err}")

        baseline_cost = max(all_gpt4o_cost, all_claude_cost)
        savings_pct = round(((baseline_cost - allocated_cost) / max(0.001, baseline_cost)) * 100, 1)

        return {
            "nodeCount": len(nodes),
            "edgeCount": graph.number_of_edges(),
            "totalInputTokens": total_input_tokens,
            "totalOutputTokens": total_output_tokens,
            "totalTokens": total_tokens,
            "criticalPath": critical_path,
            "criticalPathLatencySec": critical_path_latency,
            "agentDistribution": agent_counts,
            "comparison": {
                "allGpt4oCost": round(all_gpt4o_cost, 4),
                "allClaudeCost": round(all_claude_cost, 4),
                "allGeminiCost": round(all_gemini_cost, 4),
                "dietCodeOptimizedCost": round(allocated_cost, 4),
                "savingsPercentVsBaseline": max(0.0, savings_pct)
            }
        }
