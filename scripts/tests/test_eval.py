"""Tests for eval.py cost and anonymous-model handling, run without Kilo."""

import json
import sys

import aggregate_metrics
import eval as eval_script
import pytest
from eval import TIMEOUT_RETURNCODE, KiloResponse


def step_finish(cost, model="m"):
    return {
        "type": "step_finish",
        "part": {"cost": cost, "tokens": {"input": 1, "output": 2}, "model": {"modelID": model}},
    }


def response(events, returncode=0):
    return KiloResponse("out", "prompt", 1.0, model="m", events=events, returncode=returncode)


def test_cost_sums_step_costs():
    assert response([step_finish(0.01), step_finish(0.02)]).cost == pytest.approx(0.03)


def test_free_model_cost_is_a_known_zero():
    """A completed free call reports a real 0.0, which must not read as unknown."""
    assert response([step_finish(0.0)]).cost == 0.0


def test_timed_out_cost_is_unknown():
    """The timeout drops the event stream, so charges already incurred are unrecoverable."""
    timed_out = response([], returncode=TIMEOUT_RETURNCODE)
    assert timed_out.timed_out
    assert timed_out.cost is None
    assert timed_out.to_dict()["cost"] is None


def test_unknown_cost_stays_unknown_through_aggregation():
    """A timed-out call must neither count as free nor skew the average cost difference."""
    known = {"tokens_output": 1, "execution_time": 1.0, "cost": 0.02, "has_code": True}
    unknown = {"tokens_output": 1, "execution_time": 1.0, "cost": None, "timed_out": True}
    comparison = aggregate_metrics._condition_comparison(known, unknown)
    assert "cost_difference" not in comparison

    metrics = {"q": {"m": {"with_skills": known, "without_skills": unknown}}}
    aggregate = aggregate_metrics.generate_comparison_summary(metrics)["aggregate"]["m"]
    assert "avg_cost_difference" not in aggregate


def test_anonymous_env_strips_credentials_but_keeps_permissions(monkeypatch):
    config = {
        "provider": {"kilo": {"options": {"apiKey": "{env:KILO_API_KEY}"}}},
        "permission": {"bash": {"*": "deny"}},
    }
    monkeypatch.setenv("KILO_API_KEY", "secret")
    monkeypatch.setenv("KILO_CONFIG_CONTENT", json.dumps(config))

    env = eval_script._anonymous_env("/tmp/anon")

    assert "KILO_API_KEY" not in env
    assert env["XDG_DATA_HOME"] == "/tmp/anon"
    assert json.loads(env["KILO_CONFIG_CONTENT"]) == {"permission": {"bash": {"*": "deny"}}}


@pytest.mark.parametrize(
    ("argv", "unmatched"),
    [
        (["--models", "a/b", "--anonymous-models", "a/c"], "a/c"),
        (["--anonymous-models", "a/b"], "a/b"),
        (["--models", "a/b", "a/c", "--anonymous-models", "a/b", "a/typo"], "a/typo"),
    ],
    ids=["misspelled", "no_models_given", "one_of_two_unmatched"],
)
def test_unmatched_anonymous_model_is_rejected(monkeypatch, capsys, argv, unmatched):
    """An unmatched name would otherwise run authenticated while recorded as anonymous."""
    monkeypatch.setattr(sys, "argv", ["eval.py", *argv])
    with pytest.raises(SystemExit) as exc:
        eval_script.main()
    assert exc.value.code == 2
    assert unmatched in capsys.readouterr().err
