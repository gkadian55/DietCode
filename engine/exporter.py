"""Project Codebase Exporter for DietCode.

Extracts deliverables from executed DAG nodes, generates documentation,
builds a clean file hierarchy on disk, and bundles a .zip archive.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any


class ProjectExporter:
    """Exports generated DAG deliverables to disk and in-memory zip archives."""

    def __init__(self, export_root: Path | str | None = None) -> None:
        if export_root:
            self.export_root = Path(export_root)
        else:
            self.export_root = Path(__file__).resolve().parents[1] / "exports"
        self.export_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _clean_slug(text: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
        return slug[:36] if slug else "dietcode_project"

    def export(
        self,
        goal: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]] | None = None,
        aggregates: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Extracts deliverables and writes a complete, organized codebase folder + zip."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = self._clean_slug(goal)
        folder_name = f"{slug}_{timestamp}"
        out_dir = self.export_root / folder_name
        out_dir.mkdir(parents=True, exist_ok=True)

        exported_files: list[dict[str, Any]] = []

        for idx, node in enumerate(nodes, start=1):
            data = node.get("data", {})
            title = data.get("title", f"Task {idx}")
            category = data.get("category", "General")
            output_text = data.get("executionOutput", "")

            # If node was executed and has deliverables
            if output_text and output_text.strip():
                file_path, code_content = self._extract_code_file(output_text, title, category, idx)
                target_file = out_dir / file_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write(code_content)
                exported_files.append({
                    "path": file_path,
                    "category": category,
                    "task": title,
                    "size": len(code_content),
                    "isExecutable": True,
                })
            else:
                # If node has not been executed yet, export prompt specification blueprint
                file_path = f"specs/task_{idx:02d}_{self._clean_slug(category)}.md"
                target_file = out_dir / file_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                spec_content = (
                    f"# Task Blueprint: {title}\n\n"
                    f"- **Category**: {category}\n"
                    f"- **Assigned Model**: {data.get('assignedAgent', 'Auto-Routed')}\n"
                    f"- **Predicted Tokens**: In {data.get('predictedTokens', {}).get('input', 0):,} / Out {data.get('predictedTokens', {}).get('output', 0):,}\n\n"
                    f"## Prompt & Specification Instructions\n\n{data.get('description', '')}\n"
                )
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write(spec_content)
                exported_files.append({
                    "path": file_path,
                    "category": category,
                    "task": title,
                    "size": len(spec_content),
                    "isExecutable": False,
                })

        # Generate README.md
        readme_path = out_dir / "README.md"
        readme_content = self._generate_readme(goal, nodes, exported_files, aggregates, timestamp)
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)
        exported_files.append({
            "path": "README.md",
            "category": "Documentation",
            "task": "Project Documentation",
            "size": len(readme_content),
            "isExecutable": False,
        })

        # Generate dietcode-manifest.json
        manifest_path = out_dir / "dietcode-manifest.json"
        manifest_data = {
            "version": "1.0.0",
            "generator": "DietCode Multi-LLM DAG Engine",
            "timestamp": timestamp,
            "goal": goal,
            "aggregates": aggregates or {},
            "nodes": nodes,
            "edges": edges or [],
        }
        manifest_json = json.dumps(manifest_data, indent=2)
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest_json)
        exported_files.append({
            "path": "dietcode-manifest.json",
            "category": "Metadata",
            "task": "DAG Manifest & Telemetry",
            "size": len(manifest_json),
            "isExecutable": False,
        })

        # Create ZIP archive
        zip_path = self.export_root / f"{folder_name}.zip"
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_info in exported_files:
                local_f = out_dir / file_info["path"]
                if local_f.exists():
                    zf.write(local_f, arcname=file_info["path"])

        zip_bytes = zip_buffer.getvalue()
        with open(zip_path, "wb") as f:
            f.write(zip_bytes)

        return {
            "status": "success",
            "projectName": slug,
            "folderName": folder_name,
            "exportDirectory": str(out_dir.resolve()),
            "zipPath": str(zip_path.resolve()),
            "fileCount": len(exported_files),
            "files": exported_files,
            "zipBase64": base64.b64encode(zip_bytes).decode("utf-8"),
        }

    def _extract_code_file(self, text: str, title: str, category: str, idx: int) -> tuple[str, str]:
        # 1. Search for explicit deliverable header: ### Deliverable: `path`
        m_deliv = re.search(r"Deliverable:\s*[`'\"]?([^`'\"\r\n]+)[`'\"]?", text, re.I)
        code_blocks = list(re.finditer(r"```([a-zA-Z0-9_\-\+]*)\n(.*?)```", text, re.DOTALL))

        if m_deliv and code_blocks:
            file_path = m_deliv.group(1).strip().lstrip("/\\")
            code = code_blocks[0].group(2).strip()
            return file_path, code

        # 2. Search for code blocks with filename comment on first line
        if code_blocks:
            lang = code_blocks[0].group(1).strip()
            code = code_blocks[0].group(2).strip()
            first_line = code.split("\n")[0] if code else ""
            if first_line.startswith(("#", "//", "/*")) and ("." in first_line):
                cand = re.sub(r"^[#/\*\s]+", "", first_line).strip()
                if any(cand.endswith(ext) for ext in [".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".html", ".css", ".sql", ".sh"]):
                    return cand.lstrip("/\\"), code

            # Infer appropriate extension based on language and category
            ext = {
                "python": ".py", "py": ".py",
                "javascript": ".js", "js": ".js",
                "jsx": ".jsx", "typescript": ".ts", "ts": ".ts", "tsx": ".tsx",
                "html": ".html", "css": ".css", "json": ".json", "sql": ".sql",
            }.get(lang.lower(), ".py" if "backend" in category.lower() else ".jsx" if "frontend" in category.lower() else ".md")

            clean_t = self._clean_slug(title)
            return f"src/{idx:02d}_{clean_t}{ext}", code

        return f"outputs/{idx:02d}_{self._clean_slug(title)}.md", text

    @staticmethod
    def _generate_readme(
        goal: str,
        nodes: list[dict[str, Any]],
        files: list[dict[str, Any]],
        aggregates: dict[str, Any] | None,
        timestamp: str,
    ) -> str:
        aggs = aggregates or {}
        comp = aggs.get("comparison", {})
        lines = [
            f"# {goal}",
            "",
            "> Codebase and architectural specifications generated by **DietCode Multi-LLM DAG Engine**.",
            f"> Exported on: `{timestamp}`",
            "",
            "## 📊 Tokenomics & Multi-LLM Allocation",
            "",
            f"- **Total Nodes**: {len(nodes)} DAG Tasks",
            f"- **Forecasted Input**: {aggs.get('totalInputTokens', 0):,} tokens",
            f"- **Forecasted Output**: {aggs.get('totalOutputTokens', 0):,} tokens",
            f"- **Critical Path Latency**: {aggs.get('criticalPathLatencySec', 0)}s",
            f"- **DietCode Optimized Cost**: ${comp.get('dietCodeOptimizedCost', 0):.4f}",
            f"- **Cost Savings vs Baseline**: {comp.get('savingsPercentVsBaseline', 0)}% saved",
            "",
            "## 📁 Generated Deliverables Tree",
            "",
        ]

        for f in files:
            lines.append(f"- **`{f['path']}`** ({f['category']}) — {f.get('size', 0):,} bytes")

        lines.extend([
            "",
            "## 🧩 DAG Task Sequence",
            "",
        ])

        for idx, n in enumerate(nodes, start=1):
            d = n.get("data", {})
            lines.append(f"### {idx}. {d.get('title', 'Task')}")
            lines.append(f"- **Category**: `{d.get('category', 'General')}`")
            lines.append(f"- **Assigned LLM**: `{d.get('assignedAgent', 'Auto-Routed')}`")
            lines.append(f"- **Status**: `{d.get('executionStatus', 'pending')}`")
            lines.append(f"- **Context & Prompt**: {d.get('description', '')}")
            lines.append("")

        lines.extend([
            "---",
            "Generated with [DietCode](https://github.com/gkadian55/DietCode) — Multi-Agent Resource Optimization & Tokenomics Dashboard.",
        ])

        return "\n".join(lines)

