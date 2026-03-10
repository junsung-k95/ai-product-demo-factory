"""Unit tests for DemoFactoryAgent — mocks claude_agent_sdk to avoid real API calls."""

from unittest.mock import patch

import pytest

from demo_factory.agents.demo_factory_agent import DemoFactoryAgent


class FakeResultMessage:
    result = "Demo built successfully."


class FakeSystemMessage:
    subtype = "init"
    session_id = "test-session-123"


async def fake_query(*args, **kwargs):
    yield FakeSystemMessage()
    yield FakeResultMessage()


@pytest.mark.asyncio
async def test_generate_yields_progress(tmp_path):
    agent = DemoFactoryAgent(output_dir=str(tmp_path))

    with patch("demo_factory.agents.demo_factory_agent.query", side_effect=fake_query):
        events = []
        async for progress in agent.generate(rfp="Build a simple dashboard", demo_id="test-001"):
            events.append(progress)

    types = [e.type for e in events]
    assert "log" in types
    assert "result" in types


@pytest.mark.asyncio
async def test_rfp_saved_to_disk(tmp_path):
    agent = DemoFactoryAgent(output_dir=str(tmp_path))

    with patch("demo_factory.agents.demo_factory_agent.query", side_effect=fake_query):
        async for _ in agent.generate(rfp="Test RFP content", demo_id="test-002"):
            pass

    rfp_file = tmp_path / "test-002" / "RFP.md"
    assert rfp_file.exists()
    assert "Test RFP content" in rfp_file.read_text()
