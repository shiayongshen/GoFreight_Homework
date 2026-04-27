from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).resolve().parents[1] / "eval" / "generate_dataset.py"
SPEC = spec_from_file_location("generate_dataset", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
sys.modules["generate_dataset"] = MODULE
SPEC.loader.exec_module(MODULE)

build_blueprints = MODULE.build_blueprints
build_dataset = MODULE.build_dataset


def test_generate_dataset_builds_expected_shape() -> None:
    blueprints = build_blueprints()
    query_map = {blueprint.id: f"query for {blueprint.id}" for blueprint in blueprints}

    dataset = build_dataset(blueprints, query_map)

    assert len(dataset) == 30
    assert dataset[0]["id"] == "case_001"
    assert dataset[0]["expected_result"]["place"] == "country/USA"
    assert (
        dataset[10]["expected_result"]["error_type"] == "conflicting_time_constraints"
    )


def test_generate_dataset_encodes_range_dates_for_current_eval_runner() -> None:
    blueprints = build_blueprints()
    query_map = {blueprint.id: f"query for {blueprint.id}" for blueprint in blueprints}

    dataset = build_dataset(blueprints, query_map)
    range_cases = {
        item["id"]: item for item in dataset if item["id"] in {"case_025", "case_026"}
    }

    assert range_cases["case_025"]["expected_result"]["date"] == ""
    assert range_cases["case_026"]["expected_result"]["date"] == ""
