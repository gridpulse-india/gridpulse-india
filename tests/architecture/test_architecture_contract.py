import json
from pathlib import Path

CONTRACT_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "architecture" / "architecture-contract.v1.json"
)

REQUIRED_CORE_BOUNDARIES = {
    "ingestion-runtime",
    "timescaledb",
    "query-api",
    "realtime-gateway",
    "control-api",
}

REQUIRED_COMPONENT_FIELDS = {
    "id",
    "plane",
    "status",
    "deployment",
    "state_owner",
    "idempotency_boundary",
    "concurrency_model",
    "rollback_replay_semantics",
    "failure_domain",
    "scale_trigger",
    "security_boundary",
    "dependencies",
    "graceful_degradation",
    "extraction_trigger",
}

REQUIRED_D16_COMPONENTS = {
    "poller",
    "source-http-client",
    "grid-india-parser",
    "canonical-telemetry-model",
    "telemetry-repository",
    "source-health-tracker",
    "telemetry-hypertable",
}

PLANNED_BOUNDARIES = {
    "query-api",
    "realtime-gateway",
    "control-api",
}


def load_contract() -> dict[str, object]:
    raw_contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert isinstance(raw_contract, dict)

    return raw_contract


def get_object_list(
    contract: dict[str, object],
    key: str,
) -> list[dict[str, object]]:
    raw_items = contract[key]

    assert isinstance(raw_items, list)

    items: list[dict[str, object]] = []

    for raw_item in raw_items:
        assert isinstance(raw_item, dict)
        items.append(raw_item)

    return items


def get_component_map(
    contract: dict[str, object],
) -> dict[str, dict[str, object]]:
    components = get_object_list(contract, "components")

    component_map: dict[str, dict[str, object]] = {}

    for component in components:
        component_id = component["id"]

        assert isinstance(component_id, str)
        component_map[component_id] = component

    return component_map


def test_contract_file_exists() -> None:
    assert CONTRACT_PATH.is_file()


def test_contract_freezes_d16_baseline() -> None:
    contract = load_contract()

    baseline = contract["baseline"]

    assert isinstance(baseline, dict)
    assert baseline["frozen_day"] == "D16"
    assert baseline["migration_revision"] == "61d478c2ade3"
    assert baseline["runtime_style"] == "modular-monolith"
    assert baseline["database"] == "postgresql-timescaledb"


def test_required_architecture_boundaries_exist() -> None:
    contract = load_contract()
    components = get_component_map(contract)

    assert REQUIRED_CORE_BOUNDARIES <= components.keys()


def test_every_component_has_explicit_ownership_and_failure_rules() -> None:
    contract = load_contract()
    components = get_object_list(contract, "components")

    for component in components:
        assert REQUIRED_COMPONENT_FIELDS <= component.keys()

        for field in REQUIRED_COMPONENT_FIELDS:
            value = component[field]

            assert value is not None
            assert value != ""
            assert value != []


def test_only_control_and_data_planes_are_used() -> None:
    contract = load_contract()
    components = get_object_list(contract, "components")

    for component in components:
        assert component["plane"] in {"control", "data"}


def test_d16_ingestion_remains_existing_modular_monolith() -> None:
    contract = load_contract()
    components = get_component_map(contract)

    ingestion = components["ingestion-runtime"]

    assert ingestion["status"] == "existing"
    assert ingestion["deployment"] == "modular-monolith"


def test_timescaledb_remains_existing_state_owner() -> None:
    contract = load_contract()
    components = get_component_map(contract)

    timescaledb = components["timescaledb"]

    assert timescaledb["status"] == "existing"
    assert timescaledb["state_owner"] == "canonical-telemetry"


def test_planned_services_are_not_falsely_marked_existing() -> None:
    contract = load_contract()
    components = get_component_map(contract)

    for component_id in PLANNED_BOUNDARIES:
        component = components[component_id]

        assert component["status"] == "planned"
        assert component["deployment"] == "not-yet-extracted"


def test_every_planned_service_has_an_extraction_trigger() -> None:
    contract = load_contract()
    components = get_component_map(contract)

    for component_id in PLANNED_BOUNDARIES:
        extraction_trigger = components[component_id]["extraction_trigger"]

        assert isinstance(extraction_trigger, str)
        assert extraction_trigger.strip()


def test_d16_components_are_traceable_into_target_architecture() -> None:
    contract = load_contract()
    traceability = get_object_list(contract, "baseline_traceability")

    traced_components = {item["d16_component"] for item in traceability}

    assert traced_components == REQUIRED_D16_COMPONENTS


def test_ingestion_idempotency_boundary_matches_d16_database_design() -> None:
    contract = load_contract()
    components = get_component_map(contract)

    ingestion = components["ingestion-runtime"]

    assert ingestion["idempotency_boundary"] == "event_id+observed_at"


def test_event_backbone_is_explicitly_deferred() -> None:
    contract = load_contract()

    event_backbone = contract["event_backbone"]

    assert isinstance(event_backbone, dict)
    assert event_backbone["status"] == "deferred"
    assert event_backbone["earliest_planned_day"] == "D50"


def test_future_performance_numbers_are_not_claimed_as_measured() -> None:
    contract = load_contract()

    budgets = contract["budgets"]

    assert isinstance(budgets, dict)

    status = budgets["status"]

    assert status == "provisional-design-targets-not-measured-production-slos"

    for path_name in ("query", "realtime", "control"):
        path_budget = budgets[path_name]

        assert isinstance(path_budget, dict)
        assert path_budget["measured"] is False


def test_control_plane_failure_does_not_require_data_plane_shutdown() -> None:
    contract = load_contract()

    planes = contract["planes"]

    assert isinstance(planes, dict)

    data_plane = planes["data"]
    control_plane = planes["control"]

    assert isinstance(data_plane, dict)
    assert isinstance(control_plane, dict)

    assert data_plane["must_continue_when_control_plane_is_unavailable"] is True
    assert control_plane["may_interrupt_existing_valid_data_plane_configuration"] is False


def test_monorepo_paths_have_one_declared_owner() -> None:
    contract = load_contract()
    ownership = get_object_list(contract, "monorepo_ownership")

    paths = [item["path"] for item in ownership]

    assert len(paths) == len(set(paths))


def test_communication_owners_are_explicit() -> None:
    contract = load_contract()
    communications = get_object_list(contract, "communication")

    for communication in communications:
        timeout_owner = communication["timeout_owner"]
        retry_owner = communication["retry_owner"]

        assert isinstance(timeout_owner, str)
        assert timeout_owner.strip()

        assert isinstance(retry_owner, str)
        assert retry_owner.strip()


def test_observability_contract_requires_correlation_identifiers() -> None:
    contract = load_contract()

    observability = contract["observability_contract"]

    assert isinstance(observability, dict)

    assert "correlation_id" in observability
    assert "request_id" in observability
    assert "run_id" in observability

    required_signals = observability["required_signals"]

    assert isinstance(required_signals, list)

    assert {
        "latency",
        "success-total",
        "error-total",
        "dependency-health",
        "freshness-or-lag",
        "resource-consumption",
    } == set(required_signals)
