import os
import re
from typing import List, Dict, Any

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MEMORY_BASE_DIR = os.path.join(WORKSPACE_ROOT, "memory")
MEMORY_INDEX_PATH = os.path.join(MEMORY_BASE_DIR, "MEMORY_INDEX.md")


class MemoryIndexer:
    """
    Relational tagged memory filesystem indexer.
    Scans memory/ subdirectories (incidents, decisions, patterns)
    and maintains MEMORY_INDEX.md.
    """

    SUBDIRS = {
        "incidents": "Incident",
        "decisions": "Decision",
        "patterns": "Pattern",
    }

    def __init__(self, memory_dir: str = MEMORY_BASE_DIR):
        self.memory_dir = memory_dir
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        os.makedirs(self.memory_dir, exist_ok=True)
        for folder in self.SUBDIRS.keys():
            os.makedirs(os.path.join(self.memory_dir, folder), exist_ok=True)

    def scan_memory_files(self) -> List[Dict[str, str]]:
        entries = []
        for folder, item_type in self.SUBDIRS.items():
            folder_path = os.path.join(self.memory_dir, folder)
            if not os.path.exists(folder_path):
                continue

            for filename in sorted(os.listdir(folder_path)):
                if not filename.endswith(".md"):
                    continue

                rel_path = f"memory/{folder}/{filename}"
                filepath = os.path.join(folder_path, filename)
                
                item_id = filename.split("-")[0] if "-" in filename else filename.replace(".md", "")
                title, keywords = self._extract_metadata(filepath)

                entries.append({
                    "id": item_id,
                    "type": item_type,
                    "title": title,
                    "keywords": keywords,
                    "path": rel_path,
                })

        return entries

    def _extract_metadata(self, filepath: str) -> tuple[str, str]:
        title = os.path.basename(filepath).replace(".md", "")
        keywords = "general"

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()

            kw_match = re.search(r"Kulcsszavak:\s*`([^`]+)`", content, re.IGNORECASE)
            if kw_match:
                keywords = kw_match.group(1).strip()
            else:
                # Infer keywords from text tokens
                tokens = re.findall(r"\b[a-zA-Z0-9_\-]{4,}\b", content.lower())
                unique_tokens = list(set(tokens[:5]))
                if unique_tokens:
                    keywords = ", ".join(unique_tokens)

        except Exception:
            pass

        return title, keywords

    def rebuild_index(self) -> str:
        entries = self.scan_memory_files()

        lines = [
            "# MEMORY INDEX",
            "",
            "| ID | Típus | Cím / Probléma | Kulcsszavak | Fájl Útvonal |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]

        for e in entries:
            lines.append(
                f"| **{e['id']}** | {e['type']} | {e['title']} | `{e['keywords']}` | `{e['path']}` |"
            )

        lines.append("")
        content = "\n".join(lines)

        with open(MEMORY_INDEX_PATH, "w", encoding="utf-8") as f:
            f.write(content)

        return content
