from src.core.enums import ActionType
from src.ai.utility_ai import ActionCandidate, choose_best, weighted_sum


def test_choose_best_picks_maximum_utility():
    candidates = [
        ActionCandidate(action=ActionType.PASS, utility=12.0),
        ActionCandidate(action=ActionType.SHOOT, utility=34.0),
        ActionCandidate(action=ActionType.DRIBBLE, utility=20.0),
    ]
    best = choose_best(candidates)
    assert best.action == ActionType.SHOOT
    assert best.utility == 34.0


def test_choose_best_returns_none_for_empty_list():
    assert choose_best([]) is None


def test_weighted_sum_adds_components():
    assert weighted_sum({"a": 1.0, "b": -2.5, "c": 4.0}) == 2.5


def test_explanation_lines_include_action_and_components():
    cand = ActionCandidate(action=ActionType.PASS, utility=18.0,
                            components={"PassingLaneQuality": 10.0, "InterceptionRisk": -4.0},
                            reasons=["High-quality passing lane"])
    lines = cand.explanation_lines()
    assert lines[0].startswith("PASS")
    assert any("PassingLaneQuality" in l for l in lines)
    assert any("High-quality passing lane" in l for l in lines)
