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
                depth=depth
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
        """Decomposes goals into specialized subtasks with clear domain boundaries."""
        clean_goal = goal.strip()
        lower_goal = clean_goal.lower()

        # Dynamic architectural module detection
        has_db = any(w in lower_goal for w in ["db", "database", "sql", "postgres", "mongo", "prisma", "storage", "schema"])
        has_auth = any(w in lower_goal for w in ["auth", "security", "jwt", "oauth", "rbac", "user", "session", "login"])
        has_cache = any(w in lower_goal for w in ["cache", "redis", "memcached", "in-memory"])
        has_queue = any(w in lower_goal for w in ["kafka", "queue", "stream", "pub-sub", "pubsub", "event", "worker", "rabbitmq", "celery", "distributed"])
        has_ml = any(w in lower_goal for w in ["ai", "model", "llm", "agent", "train", "forecast", "embed", "rag", "onnx", "quantiz"])
        has_api = any(w in lower_goal for w in ["api", "rest", "graphql", "grpc", "gateway", "endpoint", "microservice"])
        has_ui = any(w in lower_goal for w in ["ui", "frontend", "dashboard", "canvas", "web", "react", "client", "visual", "view"])
        has_devops = any(w in lower_goal for w in ["docker", "k8s", "kubernetes", "deploy", "ci", "cd", "cluster", "cloud", "infra"])
        has_obs = any(w in lower_goal for w in ["observability", "metrics", "telemetry", "tracing", "monitoring", "log", "latency"])

        # 1. Root Architecture Node
        tasks: list[dict[str, Any]] = [
            {
                "id": "node-arch",
                "title": "System Architecture & Protocol Spec",
                "description": f"Formalize requirements, domain boundary specifications, and communication contracts for '{clean_goal}'.",
                "category": "Architecture",
                "dependencies": []
            }
        ]

        # 2. Database Schema (if requested or complex)
        if has_db or not (has_ml or has_queue):
            tasks.append({
                "id": "node-db",
                "title": "Data Schema, Migrations & Indexing",
                "description": "Formulate persistent models, transactional constraints, relational indexes, and migration scripts.",
                "category": "Database",
                "dependencies": ["node-arch"]
            })

        # 3. Auth & Access Control
        if has_auth:
            db_dep = ["node-db"] if any(t["id"] == "node-db" for t in tasks) else ["node-arch"]
            tasks.append({
                "id": "node-auth",
                "title": "Auth, JWT & Role-Based Access Control",
                "description": "Implement cryptographic token signing, session rotation, RBAC middleware, and credential verification.",
                "category": "Security",
                "dependencies": db_dep
            })

        # 4. In-Memory Caching
        if has_cache:
            db_dep = ["node-db"] if any(t["id"] == "node-db" for t in tasks) else ["node-arch"]
            tasks.append({
                "id": "node-cache",
                "title": "High-Throughput In-Memory Caching",
                "description": "Deploy cache eviction policies (LRU/TTL), connection pooling, and serialized key-value caching.",
                "category": "Performance",
                "dependencies": db_dep
            })

        # 5. Distributed Queues & Event Streaming
        if has_queue:
            tasks.append({
                "id": "node-queue",
                "title": "Distributed Event Bus & Worker Pipeline",
                "description": "Establish partitioned event pub-sub streaming, backpressure handling, and asynchronous workers.",
                "category": "Distributed Systems",
                "dependencies": ["node-arch"]
            })

        # 6. Core Processing Engine
        core_deps = ["node-arch"]
        if any(t["id"] == "node-db" for t in tasks):
            core_deps.append("node-db")
        if any(t["id"] == "node-queue" for t in tasks):
            core_deps.append("node-queue")

        tasks.append({
            "id": "node-core",
            "title": "Core Algorithmic Engine & Business Logic",
            "description": "Construct low-latency stateful execution services, domain rule evaluators, and atomic workflows.",
            "category": "Backend",
            "dependencies": core_deps
        })

        # 7. Machine Learning & Embeddings
        if has_ml:
            ml_dep = ["node-core"]
            if any(t["id"] == "node-db" for t in tasks):
                ml_dep.append("node-db")
            tasks.append({
                "id": "node-ml",
                "title": "Local ML Pipeline & Token Forecaster",
                "description": "Feature vectorization, local GGUF/ONNX model inference, quantization, and tensor caching.",
                "category": "Machine Learning",
                "dependencies": ml_dep
            })

        # 8. API Gateway & RPC
        if has_api or has_ui:
            api_deps = ["node-core"]
            if any(t["id"] == "node-auth" for t in tasks):
                api_deps.append("node-auth")
            tasks.append({
                "id": "node-api",
                "title": "API Gateway & High-Speed Interfaces",
                "description": "Expose typed REST/gRPC endpoints, schema validation, rate-limiting, and error handlers.",
                "category": "API Layer",
                "dependencies": api_deps
            })

        # 9. Client UI & Canvas
        if has_ui or len(tasks) < 5:
            ui_dep = ["node-api"] if any(t["id"] == "node-api" for t in tasks) else ["node-core"]
            tasks.append({
                "id": "node-ui",
                "title": "Client UI & Reactive State Dashboard",
                "description": "Render interactive canvas views, live telemetry charts, micro-animations, and client state sync.",
                "category": "Frontend",
                "dependencies": ui_dep
            })

        # 10. Containerization & DevOps
        if has_devops:
            devops_dep = ["node-core"]
            if any(t["id"] == "node-ui" for t in tasks):
                devops_dep.append("node-ui")
            tasks.append({
                "id": "node-devops",
                "title": "Containerization & Infrastructure as Code",
                "description": "Multi-stage Docker builds, Kubernetes manifests, health probes, and automated CI/CD stages.",
                "category": "DevOps",
                "dependencies": devops_dep
            })

        # 11. Observability & Tracing
        if has_obs or len(tasks) >= 6:
            obs_deps = ["node-core"]
            if any(t["id"] == "node-api" for t in tasks):
                obs_deps.append("node-api")
            tasks.append({
                "id": "node-obs",
                "title": "Telemetry & Distributed Tracing",
                "description": "Integrate OpenTelemetry metrics, Prometheus scrapers, structured logging, and latency tracing.",
                "category": "Observability",
                "dependencies": obs_deps
            })

        # 12. Automated Testing Suite (Terminal node)
        qa_deps = []
        if any(t["id"] == "node-ui" for t in tasks):
            qa_deps.append("node-ui")
        elif any(t["id"] == "node-api" for t in tasks):
            qa_deps.append("node-api")
        else:
            qa_deps.append("node-core")

        if any(t["id"] == "node-obs" for t in tasks):
            qa_deps.append("node-obs")

        tasks.append({
            "id": "node-qa",
            "title": "Automated End-to-End & Stress Testing",
            "description": "Execute contract tests, chaos resilience injection, integration mocks, and load benchmarks.",
            "category": "QA & Testing",
            "dependencies": qa_deps
        })

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
