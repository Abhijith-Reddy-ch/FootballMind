from src.core.enums import Mentality, TacticalStyle
from src.ai.tactics import STYLE_PRESETS, dynamic_adaptation, preset_for


def test_style_presets_are_distinct():
    possession = STYLE_PRESETS[TacticalStyle.POSSESSION]
    counter = STYLE_PRESETS[TacticalStyle.COUNTER_ATTACK]
    high_press = STYLE_PRESETS[TacticalStyle.HIGH_PRESS]
    defensive = STYLE_PRESETS[TacticalStyle.DEFENSIVE]

    assert high_press.pressing_intensity > possession.pressing_intensity
    assert counter.passing_risk > possession.passing_risk
    assert defensive.defensive_line < possession.defensive_line


def test_losing_late_increases_attacking_settings():
    base = preset_for(TacticalStyle.BALANCED)
    adjusted, reasons = dynamic_adaptation(base, minute=80.0, own_score=0, opp_score=1)
    assert reasons
    assert adjusted.mentality == Mentality.ATTACK
    assert adjusted.pressing_intensity > base.pressing_intensity
    assert adjusted.defensive_line > base.defensive_line
    assert adjusted.passing_risk > base.passing_risk


def test_winning_late_decreases_risk():
    base = preset_for(TacticalStyle.BALANCED)
    adjusted, reasons = dynamic_adaptation(base, minute=88.0, own_score=1, opp_score=0)
    assert reasons
    assert adjusted.mentality == Mentality.DEFEND
    assert adjusted.pressing_intensity < base.pressing_intensity
    assert adjusted.passing_risk < base.passing_risk


def test_no_adaptation_when_scores_level_or_early():
    base = preset_for(TacticalStyle.BALANCED)
    adjusted, reasons = dynamic_adaptation(base, minute=80.0, own_score=1, opp_score=1)
    assert reasons == []
    assert adjusted == base

    adjusted2, reasons2 = dynamic_adaptation(base, minute=40.0, own_score=0, opp_score=1)
    assert reasons2 == []
    assert adjusted2 == base


def test_very_late_adaptation_stronger_than_late():
    base = preset_for(TacticalStyle.BALANCED)
    late, _ = dynamic_adaptation(base, minute=76.0, own_score=0, opp_score=1)
    very_late, _ = dynamic_adaptation(base, minute=86.0, own_score=0, opp_score=1)
    assert very_late.pressing_intensity >= late.pressing_intensity
