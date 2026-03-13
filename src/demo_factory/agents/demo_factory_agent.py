"""
Core demo generation engine powered by Claude Code (claude_agent_sdk).

Instead of calling the Claude LLM API to generate code strings,
this module spawns a Claude Code agent that autonomously:
  - Reads the RFP
  - Creates project files (Write/Edit tools)
  - Installs dependencies (Bash)
  - Runs & debugs the demo (Bash)
  - Fixes errors iteratively
"""

import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, SystemMessage, query
from claude_agent_sdk.types import AssistantMessage, TextBlock

from demo_factory.config import settings

logger = logging.getLogger(__name__)


@dataclass
class DemoProgress:
    demo_id: str
    type: str  # "log" | "result" | "error" | "session"
    content: str
    session_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class DemoResult:
    demo_id: str
    status: str  # "success" | "error"
    demo_path: str
    session_id: str | None
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


SYSTEM_PROMPT = """You are an expert full-stack developer building flashy, impressive product demos.
Your goal: given an RFP (Request for Proposal), build a fully-functional, visually stunning demo.

Rules:
- Always create an index.html that opens directly in a browser (no build step required)
- Use CDN links for all JS/CSS libraries (Tailwind, Chart.js, Alpine.js, etc.)
- If a backend is needed, create a minimal Python FastAPI server (main.py) with inline instructions
- Prefer single-file demos when possible — they're easier to share
- Make the UI look professional: gradients, animations, responsive layout
- If the RFP mentions AI features, add them using the Anthropic Messages API (claude-opus-4-6)
- Test the demo by opening any HTML files and checking for obvious errors
- Write a README_demo.md with: what was built, how to run it, key features

Never ask clarifying questions — make reasonable assumptions and build something impressive.
"""

VERIFY_PROMPT = """Review the demo you just built:
1. Check all files exist and have no obvious syntax errors
2. Verify index.html is self-contained and references correct paths
3. If there's a backend (main.py), confirm it has all required imports and endpoints
4. List the files created and their purpose in a brief summary

Do NOT rebuild from scratch — only fix critical issues if found."""


class DemoFactoryAgent:
    """
    Generates product demos autonomously using a Claude Code agent.

    Usage:
        agent = DemoFactoryAgent()
        async for progress in agent.generate(rfp="Build a logistics dashboard..."):
            print(progress.content)
    """

    def __init__(self, output_dir: str | None = None) -> None:
        self.output_dir = Path(output_dir or settings.demos_output_dir)

    async def generate(self, rfp: str, demo_id: str | None = None) -> AsyncIterator[DemoProgress]:
        """
        Generate a demo from an RFP.
        Yields DemoProgress events (logs, session info, final result).
        """
        demo_id = demo_id or str(uuid.uuid4())[:8]
        demo_dir = self.output_dir / demo_id
        demo_dir.mkdir(parents=True, exist_ok=True)

        # Save RFP for reference
        (demo_dir / "RFP.md").write_text(f"# RFP\n\n{rfp}\n")

        session_id: str | None = None

        yield DemoProgress(
            demo_id=demo_id, type="log", content=f"Starting demo generation in {demo_dir}"
        )

        # ── Phase 1: Build the demo ──────────────────────────────────────────
        try:
            async for progress in self._run_phase(
                demo_id=demo_id,
                demo_dir=demo_dir,
                prompt=self._build_prompt(rfp),
                phase="build",
                session_id=None,
            ):
                if progress.session_id:
                    session_id = progress.session_id
                yield progress
        except Exception as e:
            logger.exception("Build phase failed for demo %s", demo_id)
            yield DemoProgress(demo_id=demo_id, type="error", content=f"Build phase error: {e}")
            return

        # ── Phase 2: Verify & fix ────────────────────────────────────────────
        yield DemoProgress(demo_id=demo_id, type="log", content="Verifying demo...")
        try:
            async for progress in self._run_phase(
                demo_id=demo_id,
                demo_dir=demo_dir,
                prompt=VERIFY_PROMPT,
                phase="verify",
                session_id=session_id,
            ):
                yield progress
        except Exception as e:
            logger.warning("Verify phase failed for demo %s: %s", demo_id, e)
            yield DemoProgress(demo_id=demo_id, type="log", content=f"Verify skipped: {e}")

        # ── Done ─────────────────────────────────────────────────────────────
        files = sorted(str(p.relative_to(demo_dir)) for p in demo_dir.rglob("*") if p.is_file())
        files_list = "\n".join(f"  - {f}" for f in files)
        yield DemoProgress(
            demo_id=demo_id,
            type="result",
            session_id=session_id,
            content=f"Demo ready at {demo_dir}\n\nFiles created:\n{files_list}",
        )

    async def _run_phase(
        self,
        demo_id: str,
        demo_dir: Path,
        prompt: str,
        phase: str,
        session_id: str | None,
    ) -> AsyncIterator[DemoProgress]:
        options = ClaudeAgentOptions(
            cwd=str(demo_dir),
            system_prompt=SYSTEM_PROMPT if phase == "build" else None,
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            permission_mode="acceptEdits",
            max_turns=settings.max_turns_per_demo,
            max_budget_usd=settings.max_budget_usd,
            resume=session_id,
        )

        async for message in query(prompt=prompt, options=options):
            if isinstance(message, SystemMessage) and message.subtype == "init":
                sid = message.session_id
                yield DemoProgress(
                    demo_id=demo_id,
                    type="session",
                    content=f"Agent session started: {sid}",
                    session_id=sid,
                )

            elif isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock) and block.text.strip():
                        yield DemoProgress(
                            demo_id=demo_id,
                            type="log",
                            content=block.text,
                            session_id=session_id,
                        )

            elif isinstance(message, ResultMessage):
                yield DemoProgress(
                    demo_id=demo_id,
                    type="log",
                    content=f"[Phase: {phase}] {message.result}",
                    session_id=session_id,
                )

    def _build_prompt(self, rfp: str) -> str:
        return f"""Build a complete, production-quality demo for the following RFP.

--- RFP START ---
{rfp}
--- RFP END ---

Requirements:
1. Create index.html — the main entry point (must work by opening in a browser)
2. Include impressive visuals: animations, charts, modern UI components
3. Add realistic mock data to make the demo feel alive
4. If AI/chat features are mentioned, implement them using the Anthropic API
5. All code must be complete and runnable — no placeholder comments like "// TODO"
6. Create README_demo.md explaining what was built and how to run it

Go build it now. Be creative and make it impressive!
"""
