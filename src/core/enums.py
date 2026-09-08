"""Shared enumerations used across the simulation, agent and AI layers."""
from enum import Enum, auto


class Side(Enum):
    HOME = "HOME"
    AWAY = "AWAY"


class PlayerRole(Enum):
    GK = "GK"
    CB = "CB"
    FB = "FB"        # fullback (left/right)
    CDM = "CDM"       # ball-winning / defensive midfielder
    CM = "CM"
    CAM = "CAM"       # playmaker
    WING = "WING"     # winger
    ST = "ST"         # striker


class PlayerState(Enum):
    IDLE = auto()
    POSITIONING = auto()
    ATTACKING = auto()
    DEFENDING = auto()
    PRESSING = auto()
    MARKING = auto()
    RECEIVING = auto()
    DRIBBLING = auto()
    PASSING = auto()
    SHOOTING = auto()
    TACKLING = auto()
    RECOVERING = auto()
    SUPPORT_ATTACK = auto()


class ActionType(Enum):
    MOVE = auto()
    PASS = auto()
    SHOOT = auto()
    DRIBBLE = auto()
    TACKLE = auto()
    INTERCEPT = auto()
    PRESS = auto()
    MARK = auto()
    HOLD_POSITION = auto()
    SUPPORT_ATTACK = auto()
    RETREAT = auto()
    CLEAR_BALL = auto()
    CROSS = auto()


class TacticalStyle(Enum):
    POSSESSION = "Possession"
    COUNTER_ATTACK = "Counter Attack"
    HIGH_PRESS = "High Press"
    DEFENSIVE = "Defensive"
    BALANCED = "Balanced"


class Mentality(Enum):
    ATTACK = "Attack"
    BALANCED = "Balanced"
    DEFEND = "Defend"


class MatchPhase(Enum):
    KICKOFF = "Kickoff"
    FIRST_HALF = "First Half"
    HALFTIME = "Halftime"
    SECOND_HALF = "Second Half"
    FULL_TIME = "Full Time"


class Card(Enum):
    YELLOW = "Yellow"
    RED = "Red"


class AILevel(Enum):
    """Baseline vs advanced AI configurations used for experiment mode comparisons."""
    RANDOM = "Random/Basic"
    RULE_BASED = "Rule-Based"
    UTILITY_BASED = "Utility-Based"
    FULL_MULTI_AGENT = "Full Multi-Agent"
