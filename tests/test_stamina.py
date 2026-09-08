from src.core.enums import PlayerRole, Side
from src.core.vector import v
from src.agents.player import Attributes, Player


def make_player(stamina_attr=60):
    return Player(id="p1", number=9, name="Test", role=PlayerRole.ST, side=Side.HOME,
                  attributes=Attributes(stamina=stamina_attr), position=v(0.0, 0.0))


def test_sprinting_drains_more_than_jogging():
    sprinter = make_player()
    jogger = make_player()
    sprinter.move_towards(v(20.0, 0.0), dt=1.0, sprint=True)
    jogger.move_towards(v(20.0, 0.0), dt=1.0, sprint=False)
    assert sprinter.stamina < jogger.stamina


def test_low_stamina_reduces_effective_speed():
    p = make_player()
    fresh_speed = p.effective_speed()
    p.stamina = 10.0
    tired_speed = p.effective_speed()
    assert tired_speed < fresh_speed


def test_regen_increases_stamina_up_to_max():
    p = make_player()
    p.stamina = 50.0
    p.regen_stamina(dt=5.0, intensity=0.0)
    assert p.stamina > 50.0
    assert p.stamina <= 100.0


def test_higher_stamina_attribute_drains_slower():
    fit = make_player(stamina_attr=95)
    unfit = make_player(stamina_attr=20)
    fit.move_towards(v(20.0, 0.0), dt=1.0, sprint=True)
    unfit.move_towards(v(20.0, 0.0), dt=1.0, sprint=True)
    assert fit.stamina > unfit.stamina


def test_red_carded_player_has_zero_speed():
    p = make_player()
    p.red_carded = True
    assert p.effective_speed() == 0.0
