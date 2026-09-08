import pytest

from src.core.enums import PlayerRole
from src.ai.positioning import FORMATIONS, anchor_position, slots_for
from src.ai.tactics import preset_for
from src.core.enums import TacticalStyle
from src.game import pitch


@pytest.mark.parametrize("name", list(FORMATIONS.keys()))
def test_every_formation_has_eleven_slots_with_one_gk(name):
    slots = slots_for(name)
    assert len(slots) == 11
    gk_count = sum(1 for role, *_ in slots if role == PlayerRole.GK)
    assert gk_count == 1


def test_anchor_mirrors_for_away_side():
    slots = slots_for("4-3-3")
    tactics = preset_for(TacticalStyle.BALANCED, "4-3-3")
    striker_slot = slots[-1]  # ST is advanced (x_frac close to 1) for home
    home_anchor = anchor_position(striker_slot, True, tactics, ball_x_frac=0.5)
    away_anchor = anchor_position(striker_slot, False, tactics, ball_x_frac=0.5)
    # home striker sits deep in the away half (large x); mirrored away striker sits in home half
    assert home_anchor[0] > pitch.LENGTH / 2
    assert away_anchor[0] < pitch.LENGTH / 2


def test_width_setting_spreads_wide_players_further_from_center():
    slots = slots_for("4-3-3")
    wide_slot = next(s for s in slots if s[1] == 0.76 and s[2] == 0.15)
    narrow_tactics = preset_for(TacticalStyle.BALANCED, "4-3-3")
    narrow_tactics = narrow_tactics.__class__(**{**narrow_tactics.__dict__, "width": 10})
    wide_tactics = narrow_tactics.__class__(**{**narrow_tactics.__dict__, "width": 100})

    narrow_pos = anchor_position(wide_slot, True, narrow_tactics, ball_x_frac=0.5)
    wide_pos = anchor_position(wide_slot, True, wide_tactics, ball_x_frac=0.5)

    center_y = pitch.WIDTH / 2
    assert abs(wide_pos[1] - center_y) > abs(narrow_pos[1] - center_y)


def test_defensive_line_shifts_outfield_block():
    slots = slots_for("4-3-3")
    cb_slot = next(s for s in slots if s[0] == PlayerRole.CB)
    base = preset_for(TacticalStyle.BALANCED, "4-3-3")
    deep = base.__class__(**{**base.__dict__, "defensive_line": 0})
    high = base.__class__(**{**base.__dict__, "defensive_line": 100})

    deep_pos = anchor_position(cb_slot, True, deep, ball_x_frac=0.5)
    high_pos = anchor_position(cb_slot, True, high, ball_x_frac=0.5)
    assert high_pos[0] > deep_pos[0]
