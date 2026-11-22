"""AEGIS SKILL.md Playbook Loader and Context Injector.

Built by [Abdul Hayy Khan](https://abdulhayykhan.dev).
Citations & inspirations:
- AEGIS Project Review Report (Finding M8 & Section 5 Step 4.4)
- agiprolabs/claude-trading-skills: Dynamic playbook injection based on regime state
"""

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from src.signals.regime import MarketRegime


class PlaybookDocument(BaseModel):
    """Parsed markdown playbook from skills/ directory."""
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    content: str
    path: str


class PlaybookLoader:
    """Discovers, parses, and loads SKILL.md playbooks for trading execution."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        self.skills_dir = skills_dir or (Path(__file__).parent.parent.parent / "skills")
        self._cache: dict[str, PlaybookDocument] = {}
        self._scan_and_load()

    def _scan_and_load(self) -> None:
        if not self.skills_dir.exists():
            return

        for skill_file in self.skills_dir.rglob("SKILL.md"):
            try:
                raw_text = skill_file.read_text(encoding="utf-8")
                # Parse YAML frontmatter if present
                name = skill_file.parent.name
                desc = ""
                frontmatter_match = re.search(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw_text, re.DOTALL)
                content = raw_text
                if frontmatter_match:
                    fm_text = frontmatter_match.group(1)
                    content = frontmatter_match.group(2).strip()
                    name_m = re.search(r"name:\s*(.+)", fm_text)
                    if name_m:
                        name = name_m.group(1).strip()
                    desc_m = re.search(r"description:\s*(.+)", fm_text)
                    if desc_m:
                        desc = desc_m.group(1).strip()

                doc = PlaybookDocument(
                    name=name,
                    description=desc,
                    content=content,
                    path=str(skill_file)
                )
                self._cache[name] = doc
            except OSError:
                continue

    def list_available_skills(self) -> list[str]:
        """Return names of all discovered playbooks."""
        return sorted(self._cache.keys())

    def get_playbook(self, name: str) -> PlaybookDocument | None:
        """Retrieve a specific playbook by name."""
        return self._cache.get(name)

    def select_playbooks_for_regime(self, regime: MarketRegime) -> list[str]:
        """Select relevant playbooks based on classified market regime."""
        selected: list[str] = []
        if "market-regime-detection" in self._cache:
            selected.append("market-regime-detection")

        if regime == MarketRegime.TRENDING_BULL:
            if "price-action-and-liquidity" in self._cache:
                selected.append("price-action-and-liquidity")
            if "onchain-intelligence" in self._cache:
                selected.append("onchain-intelligence")
        elif regime in (MarketRegime.TRENDING_BEAR, MarketRegime.HIGH_VOLATILITY):
            if "multi-agent-debate" in self._cache:
                selected.append("multi-agent-debate")
            if "incident-postmortem" in self._cache:
                selected.append("incident-postmortem")
        else:
            if "multi-agent-debate" in self._cache:
                selected.append("multi-agent-debate")

        return selected
