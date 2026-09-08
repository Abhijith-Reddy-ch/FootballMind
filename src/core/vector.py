"""2D vector helpers built on plain tuples/np arrays for pitch-space math."""
from __future__ import annotations

import math
from typing import Tuple

import numpy as np

Vec2 = np.ndarray


def v(x: float, y: float) -> Vec2:
    return np.array([x, y], dtype=float)


def distance(a: Vec2, b: Vec2) -> float:
    return float(np.linalg.norm(a - b))


def normalize(vec: Vec2) -> Vec2:
    n = np.linalg.norm(vec)
    if n < 1e-8:
        return np.array([0.0, 0.0])
    return vec / n


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def clamp_vec(vec: Vec2, lo: Vec2, hi: Vec2) -> Vec2:
    return np.array([clamp(vec[0], lo[0], hi[0]), clamp(vec[1], lo[1], hi[1])])


def angle_between(a: Vec2, b: Vec2) -> float:
    """Angle in degrees between two vectors (0-180)."""
    na, nb = normalize(a), normalize(b)
    dot = clamp(float(np.dot(na, nb)), -1.0, 1.0)
    return math.degrees(math.acos(dot))


def lerp(a: Vec2, b: Vec2, t: float) -> Vec2:
    return a + (b - a) * clamp(t, 0.0, 1.0)


def point_segment_distance(p: Vec2, a: Vec2, b: Vec2) -> float:
    """Shortest distance from point p to the segment a-b (used for passing-lane risk)."""
    ab = b - a
    length_sq = float(np.dot(ab, ab))
    if length_sq < 1e-8:
        return distance(p, a)
    t = clamp(float(np.dot(p - a, ab)) / length_sq, 0.0, 1.0)
    proj = a + ab * t
    return distance(p, proj)
