"""Unit tests for runner module."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import Config
from src.phases.common import PhaseResult
from src.runner import PhaseError, SimulationBusyError, TickReport, TickRunner
from src.utils.storage import (
    Character,
    CharacterIdentity,
    CharacterMemory,
    CharacterState,
    Location,
    LocationIdentity,
    LocationState,
    Simulation,
    load_simulation,
)


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Create mock config for testing."""
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[simulation]
memory_cells = 10

[phase1]
model = "gpt-4o"
timeout = 30
max_retries = 3
reasoning_effort = "low"
response_chain_depth = 5

[phase2a]
model = "gpt-4o"
timeout = 30
max_retries = 3
reasoning_effort = "low"
response_chain_depth = 0

[phase2b]
model = "gpt-4o"
timeout = 30
max_retries = 3
reasoning_effort = "low"
response_chain_depth = 0

[phase4]
model = "gpt-4o"
timeout = 30
max_retries = 3
reasoning_effort = "low"
response_chain_depth = 5
""",
        encoding="utf-8",
    )
    return Config.load(config_path=config_path, project_root=tmp_path)


@pytest.fixture
def sample_simulation() -> Simulation:
    """Create sample simulation for testing."""
    return Simulation(
        id="test-sim",
        current_tick=0,
        created_at=datetime.now(),
        status="paused",
        characters={
            "bob": Character(
                identity=CharacterIdentity(
                    id="bob",
                    name="Bob",
                    description="A test character",
                ),
                state=CharacterState(location="tavern"),
                memory=CharacterMemory(),
            ),
        },
        locations={
            "tavern": Location(
                identity=LocationIdentity(
                    id="tavern",
                    name="The Tavern",
                    description="A cozy place",
                ),
                state=LocationState(moment="Evening"),
            ),
        },
    )


def create_test_simulation_on_disk(tmp_path: Path, status: str = "paused") -> Path:
    """Create test simulation files on disk."""
    sim_path = tmp_path / "simulations" / "test-sim"
    sim_path.mkdir(parents=True)
    (sim_path / "characters").mkdir()
    (sim_path / "locations").mkdir()
    (sim_path / "logs").mkdir()

    (sim_path / "simulation.json").write_text(
        json.dumps(
            {
                "id": "test-sim",
                "current_tick": 0,
                "created_at": "2025-01-15T10:00:00Z",
                "status": status,
            }
        ),
        encoding="utf-8",
    )

    (sim_path / "characters" / "bob.json").write_text(
        json.dumps(
            {
                "identity": {"id": "bob", "name": "Bob", "description": "Test char"},
                "state": {"location": "tavern"},
                "memory": {"cells": [], "summary": ""},
            }
        ),
        encoding="utf-8",
    )

    (sim_path / "locations" / "tavern.json").write_text(
        json.dumps(
            {
                "identity": {"id": "tavern", "name": "Tavern", "description": "A place"},
                "state": {"moment": "Evening"},
            }
        ),
        encoding="utf-8",
    )

    return sim_path


class TestTickReport:
    """Tests for TickReport dataclass."""

    def test_tick_report_success(self, sample_simulation: Simulation) -> None:
        """TickReport stores success state."""
        report = TickReport(
            sim_id="my-sim",
            tick_number=42,
            narratives={"tavern": "Bob enters."},
            location_names={"tavern": "The Tavern"},
            success=True,
            timestamp=datetime.now(),
            duration=8.2,
            phases={},
            simulation=sample_simulation,
            pending_memories={},
        )

        assert report.sim_id == "my-sim"
        assert report.tick_number == 42
        assert report.narratives == {"tavern": "Bob enters."}
        assert report.location_names == {"tavern": "The Tavern"}
        assert report.success is True
        assert report.error is None
        assert report.duration == 8.2
        assert report.phases == {}
        assert report.pending_memories == {}

    def test_tick_report_failure(self, sample_simulation: Simulation) -> None:
        """TickReport stores failure state with error."""
        report = TickReport(
            sim_id="my-sim",
            tick_number=0,
            narratives={},
            location_names={},
            success=False,
            timestamp=datetime.now(),
            duration=0.0,
            phases={},
            simulation=sample_simulation,
            pending_memories={},
            error="Phase 1 failed",
        )

        assert report.success is False
        assert report.error == "Phase 1 failed"


class TestSimulationBusyError:
    """Tests for SimulationBusyError exception."""

    def test_simulation_busy_error_message(self) -> None:
        """SimulationBusyError includes sim_id in message."""
        error = SimulationBusyError("my-sim")

        assert error.sim_id == "my-sim"
        assert "my-sim" in str(error)
        assert "running" in str(error)


class TestPhaseError:
    """Tests for PhaseError exception."""

    def test_phase_error_message(self) -> None:
        """PhaseError includes phase name and error in message."""
        error = PhaseError("phase1", "LLM timeout")

        assert error.phase_name == "phase1"
        assert error.error == "LLM timeout"
        assert "phase1" in str(error)
        assert "LLM timeout" in str(error)


class TestTickRunner:
    """Tests for TickRunner class."""

    def test_tick_runner_init(self, mock_config: Config) -> None:
        """TickRunner initializes with config and narrators."""
        narrators: list = []
        runner = TickRunner(mock_config, narrators)

        assert runner._config is mock_config
        assert runner._narrators is narrators

    @pytest.mark.asyncio
    async def test_run_tick_simulation_busy(self, mock_config: Config, tmp_path: Path) -> None:
        """run_tick raises SimulationBusyError when status is running."""
        # Create simulation with running status
        sim_path = create_test_simulation_on_disk(tmp_path, status="running")
        simulation = load_simulation(sim_path)

        runner = TickRunner(mock_config, [])

        with pytest.raises(SimulationBusyError) as exc_info:
            await runner.run_tick(simulation, sim_path)

        assert exc_info.value.sim_id == "test-sim"

    @pytest.mark.asyncio
    async def test_run_tick_success(self, mock_config: Config, tmp_path: Path) -> None:
        """run_tick completes successfully and increments tick."""
        sim_path = create_test_simulation_on_disk(tmp_path)
        simulation = load_simulation(sim_path)

        # Mock all phases to succeed
        async def mock_phase1(sim, cfg, client):
            return PhaseResult(success=True, data={"bob": MagicMock(intention="test intention")})

        async def mock_phase2a(sim, cfg, client, intentions):
            return PhaseResult(
                success=True,
                data={
                    "tavern": MagicMock(
                        location_id="tavern",
                        characters={"bob": MagicMock()},
                        location=MagicMock(),
                    ),
                },
            )

        async def mock_phase2b(sim, cfg, client, master_results, intentions):
            return PhaseResult(
                success=True,
                data={
                    "tavern": MagicMock(narrative="Test narrative."),
                },
            )

        async def mock_phase3(sim, cfg, master_results):
            return PhaseResult(success=True, data={"pending_memories": {"bob": "memory"}})

        async def mock_phase4(sim, cfg, client, memories):
            return PhaseResult(success=True, data=None)

        with (
            patch("src.runner.execute_phase1", mock_phase1),
            patch("src.runner.execute_phase2a", mock_phase2a),
            patch("src.runner.execute_phase2b", mock_phase2b),
            patch("src.runner.execute_phase3", mock_phase3),
            patch("src.runner.execute_phase4", mock_phase4),
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
        ):
            runner = TickRunner(mock_config, [])
            result = await runner.run_tick(simulation, sim_path)

        assert result.success is True
        assert result.tick_number == 1
        assert result.sim_id == "test-sim"
        assert "tavern" in result.narratives
        assert result.narratives["tavern"] == "Test narrative."

    @pytest.mark.asyncio
    async def test_run_tick_phase1_fails(self, mock_config: Config, tmp_path: Path) -> None:
        """run_tick raises PhaseError when phase1 fails."""
        sim_path = create_test_simulation_on_disk(tmp_path)
        simulation = load_simulation(sim_path)

        async def mock_phase1_fail(sim, cfg, client):
            return PhaseResult(success=False, data=None, error="LLM error")

        with (
            patch("src.runner.execute_phase1", mock_phase1_fail),
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
        ):
            runner = TickRunner(mock_config, [])

            with pytest.raises(PhaseError) as exc_info:
                await runner.run_tick(simulation, sim_path)

            assert exc_info.value.phase_name == "phase1"
            assert "LLM error" in exc_info.value.error

    @pytest.mark.asyncio
    async def test_run_tick_phase2a_fails(self, mock_config: Config, tmp_path: Path) -> None:
        """run_tick raises PhaseError when phase2a fails."""
        sim_path = create_test_simulation_on_disk(tmp_path)
        simulation = load_simulation(sim_path)

        async def mock_phase1(sim, cfg, client):
            return PhaseResult(success=True, data={})

        async def mock_phase2a_fail(sim, cfg, client, intentions):
            return PhaseResult(success=False, data=None, error="Arbiter error")

        with (
            patch("src.runner.execute_phase1", mock_phase1),
            patch("src.runner.execute_phase2a", mock_phase2a_fail),
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
        ):
            runner = TickRunner(mock_config, [])

            with pytest.raises(PhaseError) as exc_info:
                await runner.run_tick(simulation, sim_path)

            assert exc_info.value.phase_name == "phase2a"

    @pytest.mark.asyncio
    async def test_run_tick_calls_narrators(self, mock_config: Config, tmp_path: Path) -> None:
        """run_tick calls all narrators after success."""
        sim_path = create_test_simulation_on_disk(tmp_path)
        simulation = load_simulation(sim_path)

        captured_results: list = []

        class MockNarrator:
            def output(self, report: TickReport) -> None:
                captured_results.append(report)

        async def mock_phase1(sim, cfg, client):
            return PhaseResult(success=True, data={})

        async def mock_phase2a(sim, cfg, client, intentions):
            return PhaseResult(success=True, data={})

        async def mock_phase2b(sim, cfg, client, master_results, intentions):
            return PhaseResult(success=True, data={})

        async def mock_phase3(sim, cfg, master_results):
            return PhaseResult(success=True, data={"pending_memories": {}})

        async def mock_phase4(sim, cfg, client, memories):
            return PhaseResult(success=True, data=None)

        with (
            patch("src.runner.execute_phase1", mock_phase1),
            patch("src.runner.execute_phase2a", mock_phase2a),
            patch("src.runner.execute_phase2b", mock_phase2b),
            patch("src.runner.execute_phase3", mock_phase3),
            patch("src.runner.execute_phase4", mock_phase4),
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
        ):
            runner = TickRunner(mock_config, [MockNarrator(), MockNarrator()])
            await runner.run_tick(simulation, sim_path)

        # Both narrators should be called
        assert len(captured_results) == 2
        assert all(r.success for r in captured_results)

    @pytest.mark.asyncio
    async def test_run_tick_narrator_failure_isolated(
        self, mock_config: Config, tmp_path: Path
    ) -> None:
        """run_tick continues if narrator fails."""
        sim_path = create_test_simulation_on_disk(tmp_path)
        simulation = load_simulation(sim_path)

        call_count = 0

        class FailingNarrator:
            def output(self, report: TickReport) -> None:
                raise RuntimeError("Narrator crashed")

        class CountingNarrator:
            def output(self, report: TickReport) -> None:
                nonlocal call_count
                call_count += 1

        async def mock_phase1(sim, cfg, client):
            return PhaseResult(success=True, data={})

        async def mock_phase2a(sim, cfg, client, intentions):
            return PhaseResult(success=True, data={})

        async def mock_phase2b(sim, cfg, client, master_results, intentions):
            return PhaseResult(success=True, data={})

        async def mock_phase3(sim, cfg, master_results):
            return PhaseResult(success=True, data={"pending_memories": {}})

        async def mock_phase4(sim, cfg, client, memories):
            return PhaseResult(success=True, data=None)

        with (
            patch("src.runner.execute_phase1", mock_phase1),
            patch("src.runner.execute_phase2a", mock_phase2a),
            patch("src.runner.execute_phase2b", mock_phase2b),
            patch("src.runner.execute_phase3", mock_phase3),
            patch("src.runner.execute_phase4", mock_phase4),
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
        ):
            # Failing narrator first, counting narrator second
            runner = TickRunner(mock_config, [FailingNarrator(), CountingNarrator()])
            result = await runner.run_tick(simulation, sim_path)

        # Tick should still succeed
        assert result.success is True
        # Second narrator should still be called
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_run_tick_increments_current_tick(
        self, mock_config: Config, tmp_path: Path
    ) -> None:
        """run_tick increments current_tick and saves to disk."""
        sim_path = create_test_simulation_on_disk(tmp_path)
        simulation = load_simulation(sim_path)

        async def mock_phase1(sim, cfg, client):
            return PhaseResult(success=True, data={})

        async def mock_phase2a(sim, cfg, client, intentions):
            return PhaseResult(success=True, data={})

        async def mock_phase2b(sim, cfg, client, master_results, intentions):
            return PhaseResult(success=True, data={})

        async def mock_phase3(sim, cfg, master_results):
            return PhaseResult(success=True, data={"pending_memories": {}})

        async def mock_phase4(sim, cfg, client, memories):
            return PhaseResult(success=True, data=None)

        with (
            patch("src.runner.execute_phase1", mock_phase1),
            patch("src.runner.execute_phase2a", mock_phase2a),
            patch("src.runner.execute_phase2b", mock_phase2b),
            patch("src.runner.execute_phase3", mock_phase3),
            patch("src.runner.execute_phase4", mock_phase4),
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
        ):
            runner = TickRunner(mock_config, [])
            result = await runner.run_tick(simulation, sim_path)

        assert result.tick_number == 1

        # Verify saved to disk
        sim_json = json.loads((sim_path / "simulation.json").read_text(encoding="utf-8"))
        assert sim_json["current_tick"] == 1
        assert sim_json["status"] == "paused"

    @pytest.mark.asyncio
    async def test_run_tick_atomicity_no_save_on_failure(
        self, mock_config: Config, tmp_path: Path
    ) -> None:
        """run_tick does not save state if phase fails."""
        sim_path = create_test_simulation_on_disk(tmp_path)
        simulation = load_simulation(sim_path)

        async def mock_phase1_fail(sim, cfg, client):
            return PhaseResult(success=False, data=None, error="Failed")

        with (
            patch("src.runner.execute_phase1", mock_phase1_fail),
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
        ):
            runner = TickRunner(mock_config, [])

            with pytest.raises(PhaseError):
                await runner.run_tick(simulation, sim_path)

        # Verify tick was NOT incremented
        sim_json = json.loads((sim_path / "simulation.json").read_text(encoding="utf-8"))
        assert sim_json["current_tick"] == 0
        assert sim_json["status"] == "paused"


class TestSyncOpenaiData:
    """Tests for _sync_openai_data method."""

    def test_sync_openai_data_characters(
        self, mock_config: Config, sample_simulation: Simulation
    ) -> None:
        """Syncs _openai data from entity dicts to character models."""
        runner = TickRunner(mock_config, [])

        # Create entity dicts with _openai data
        runner._char_entities = [
            {
                "identity": {"id": "bob"},
                "state": {},
                "_openai": {
                    "usage": {
                        "total_tokens": 1000,
                        "reasoning_tokens": 500,
                        "cached_tokens": 200,
                        "total_requests": 10,
                    }
                },
            }
        ]
        runner._loc_entities = []

        runner._sync_openai_data(sample_simulation)

        # Check data was synced to character via __pydantic_extra__
        char = sample_simulation.characters["bob"]
        char_openai = (char.__pydantic_extra__ or {}).get("_openai")
        assert char_openai is not None
        assert char_openai["usage"]["total_tokens"] == 1000

    def test_sync_openai_data_locations(
        self, mock_config: Config, sample_simulation: Simulation
    ) -> None:
        """Syncs _openai data from entity dicts to location models."""
        runner = TickRunner(mock_config, [])

        runner._char_entities = []
        runner._loc_entities = [
            {
                "identity": {"id": "tavern"},
                "state": {},
                "_openai": {
                    "usage": {
                        "total_tokens": 2000,
                        "reasoning_tokens": 1000,
                        "cached_tokens": 0,
                        "total_requests": 5,
                    }
                },
            }
        ]

        runner._sync_openai_data(sample_simulation)

        # Check data was synced to location via __pydantic_extra__
        loc = sample_simulation.locations["tavern"]
        loc_openai = (loc.__pydantic_extra__ or {}).get("_openai")
        assert loc_openai is not None
        assert loc_openai["usage"]["total_tokens"] == 2000


class TestAggregateSimulationUsage:
    """Tests for _aggregate_simulation_usage method."""

    def test_aggregate_simulation_usage(
        self, mock_config: Config, sample_simulation: Simulation
    ) -> None:
        """Aggregates usage from all entities into simulation._openai."""
        runner = TickRunner(mock_config, [])

        # Set up _openai data on entities via __pydantic_extra__
        bob = sample_simulation.characters["bob"]
        if bob.__pydantic_extra__ is None:
            object.__setattr__(bob, "__pydantic_extra__", {})
        bob.__pydantic_extra__["_openai"] = {
            "usage": {
                "total_tokens": 1000,
                "reasoning_tokens": 500,
                "cached_tokens": 100,
                "total_requests": 10,
            }
        }

        tavern = sample_simulation.locations["tavern"]
        if tavern.__pydantic_extra__ is None:
            object.__setattr__(tavern, "__pydantic_extra__", {})
        tavern.__pydantic_extra__["_openai"] = {
            "usage": {
                "total_tokens": 2000,
                "reasoning_tokens": 1000,
                "cached_tokens": 200,
                "total_requests": 5,
            }
        }

        runner._aggregate_simulation_usage(sample_simulation)

        # Check aggregated totals via __pydantic_extra__
        sim_openai = (sample_simulation.__pydantic_extra__ or {}).get("_openai")
        assert sim_openai is not None
        assert sim_openai["total_tokens"] == 3000
        assert sim_openai["reasoning_tokens"] == 1500
        assert sim_openai["cached_tokens"] == 300
        assert sim_openai["total_requests"] == 15

    def test_aggregate_empty_entities(
        self, mock_config: Config, sample_simulation: Simulation
    ) -> None:
        """Works with entities that have no _openai data."""
        runner = TickRunner(mock_config, [])

        # No _openai data on any entity
        runner._aggregate_simulation_usage(sample_simulation)

        sim_openai = (sample_simulation.__pydantic_extra__ or {}).get("_openai")
        assert sim_openai is not None
        assert sim_openai["total_tokens"] == 0
        assert sim_openai["total_requests"] == 0


class TestNarratorLifecycleNotifications:
    """Tests for narrator lifecycle notification methods."""

    @pytest.mark.asyncio
    async def test_runner_calls_on_tick_start(self, mock_config: Config, tmp_path: Path) -> None:
        """Runner calls on_tick_start on all narrators with simulation."""
        sim_path = create_test_simulation_on_disk(tmp_path)
        simulation = load_simulation(sim_path)

        captured_tick_starts: list[tuple[str, int, object]] = []

        class MockNarrator:
            def output(self, report: TickReport) -> None:
                pass

            def on_tick_start(self, sim_id: str, tick_number: int, sim: object) -> None:
                captured_tick_starts.append((sim_id, tick_number, sim))

            def on_phase_complete(self, phase_name: str, phase_data: object) -> None:
                pass

        async def mock_phase1(sim, cfg, client):
            return PhaseResult(success=True, data={})

        async def mock_phase2a(sim, cfg, client, intentions):
            return PhaseResult(success=True, data={})

        async def mock_phase2b(sim, cfg, client, master_results, intentions):
            return PhaseResult(success=True, data={})

        async def mock_phase3(sim, cfg, master_results):
            return PhaseResult(success=True, data={"pending_memories": {}})

        async def mock_phase4(sim, cfg, client, memories):
            return PhaseResult(success=True, data=None)

        with (
            patch("src.runner.execute_phase1", mock_phase1),
            patch("src.runner.execute_phase2a", mock_phase2a),
            patch("src.runner.execute_phase2b", mock_phase2b),
            patch("src.runner.execute_phase3", mock_phase3),
            patch("src.runner.execute_phase4", mock_phase4),
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
        ):
            runner = TickRunner(mock_config, [MockNarrator(), MockNarrator()])
            await runner.run_tick(simulation, sim_path)

        # Both narrators should have on_tick_start called
        assert len(captured_tick_starts) == 2
        # All calls should have correct sim_id, tick_number, and simulation
        for sim_id, tick_number, sim in captured_tick_starts:
            assert sim_id == "test-sim"
            assert tick_number == 1
            assert sim is not None  # simulation object was passed

    @pytest.mark.asyncio
    async def test_runner_calls_on_phase_complete_for_each_phase(
        self, mock_config: Config, tmp_path: Path
    ) -> None:
        """Runner calls on_phase_complete after each phase."""
        sim_path = create_test_simulation_on_disk(tmp_path)
        simulation = load_simulation(sim_path)

        captured_phase_completes: list[str] = []

        class MockNarrator:
            def output(self, report: TickReport) -> None:
                pass

            def on_tick_start(self, sim_id: str, tick_number: int, sim: object) -> None:
                pass

            def on_phase_complete(self, phase_name: str, phase_data: object) -> None:
                captured_phase_completes.append(phase_name)

        async def mock_phase1(sim, cfg, client):
            return PhaseResult(success=True, data={})

        async def mock_phase2a(sim, cfg, client, intentions):
            return PhaseResult(success=True, data={})

        async def mock_phase2b(sim, cfg, client, master_results, intentions):
            return PhaseResult(success=True, data={})

        async def mock_phase3(sim, cfg, master_results):
            return PhaseResult(success=True, data={"pending_memories": {}})

        async def mock_phase4(sim, cfg, client, memories):
            return PhaseResult(success=True, data=None)

        with (
            patch("src.runner.execute_phase1", mock_phase1),
            patch("src.runner.execute_phase2a", mock_phase2a),
            patch("src.runner.execute_phase2b", mock_phase2b),
            patch("src.runner.execute_phase3", mock_phase3),
            patch("src.runner.execute_phase4", mock_phase4),
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
        ):
            runner = TickRunner(mock_config, [MockNarrator()])
            await runner.run_tick(simulation, sim_path)

        # on_phase_complete should be called 5 times (one per phase)
        assert len(captured_phase_completes) == 5
        assert captured_phase_completes == ["phase1", "phase2a", "phase2b", "phase3", "phase4"]

    @pytest.mark.asyncio
    async def test_runner_narrator_on_tick_start_error_isolated(
        self, mock_config: Config, tmp_path: Path
    ) -> None:
        """Narrator error in on_tick_start doesn't stop tick execution."""
        sim_path = create_test_simulation_on_disk(tmp_path)
        simulation = load_simulation(sim_path)

        class FailingNarrator:
            def output(self, report: TickReport) -> None:
                pass

            def on_tick_start(self, sim_id: str, tick_number: int, sim: object) -> None:
                raise RuntimeError("on_tick_start crashed")

            def on_phase_complete(self, phase_name: str, phase_data: object) -> None:
                pass

        async def mock_phase1(sim, cfg, client):
            return PhaseResult(success=True, data={})

        async def mock_phase2a(sim, cfg, client, intentions):
            return PhaseResult(success=True, data={})

        async def mock_phase2b(sim, cfg, client, master_results, intentions):
            return PhaseResult(success=True, data={})

        async def mock_phase3(sim, cfg, master_results):
            return PhaseResult(success=True, data={"pending_memories": {}})

        async def mock_phase4(sim, cfg, client, memories):
            return PhaseResult(success=True, data=None)

        with (
            patch("src.runner.execute_phase1", mock_phase1),
            patch("src.runner.execute_phase2a", mock_phase2a),
            patch("src.runner.execute_phase2b", mock_phase2b),
            patch("src.runner.execute_phase3", mock_phase3),
            patch("src.runner.execute_phase4", mock_phase4),
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
        ):
            runner = TickRunner(mock_config, [FailingNarrator()])
            result = await runner.run_tick(simulation, sim_path)

        # Tick should still succeed despite narrator failure
        assert result.success is True

    @pytest.mark.asyncio
    async def test_runner_narrator_on_phase_complete_error_isolated(
        self, mock_config: Config, tmp_path: Path
    ) -> None:
        """Narrator error in on_phase_complete doesn't stop tick execution."""
        sim_path = create_test_simulation_on_disk(tmp_path)
        simulation = load_simulation(sim_path)

        class FailingNarrator:
            def output(self, report: TickReport) -> None:
                pass

            def on_tick_start(self, sim_id: str, tick_number: int, sim: object) -> None:
                pass

            def on_phase_complete(self, phase_name: str, phase_data: object) -> None:
                raise RuntimeError("on_phase_complete crashed")

        async def mock_phase1(sim, cfg, client):
            return PhaseResult(success=True, data={})

        async def mock_phase2a(sim, cfg, client, intentions):
            return PhaseResult(success=True, data={})

        async def mock_phase2b(sim, cfg, client, master_results, intentions):
            return PhaseResult(success=True, data={})

        async def mock_phase3(sim, cfg, master_results):
            return PhaseResult(success=True, data={"pending_memories": {}})

        async def mock_phase4(sim, cfg, client, memories):
            return PhaseResult(success=True, data=None)

        with (
            patch("src.runner.execute_phase1", mock_phase1),
            patch("src.runner.execute_phase2a", mock_phase2a),
            patch("src.runner.execute_phase2b", mock_phase2b),
            patch("src.runner.execute_phase3", mock_phase3),
            patch("src.runner.execute_phase4", mock_phase4),
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
        ):
            runner = TickRunner(mock_config, [FailingNarrator()])
            result = await runner.run_tick(simulation, sim_path)

        # Tick should still succeed despite narrator failure
        assert result.success is True
