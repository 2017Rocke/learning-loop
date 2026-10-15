"""Prevent the capacitor's open-path particle reset from implying conduction.

These authoring-only geometry checks need no Pillow, network or learner data.
They exercise every frame up to the generator's 40-second scene limit at 15fps,
including the full radius of moving symbols and each particle's identity.
"""
import importlib.util
import math
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'embedded_scenes', Path(__file__).resolve().parents[1] / 'scripts/embedded_video_scenes.py')
scenes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scenes)


class CapacitorMotionTests(unittest.TestCase):
    def test_no_electron_intersects_dielectric_or_jumps_between_plates(self):
        left, top, right, bottom = scenes.CAP_DIELECTRIC
        for path in (scenes.CHARGE_OUT, scenes.CHARGE_IN, scenes.DISCHARGE):
            with self.subTest(path=path):
                length = sum(math.dist(a,b) for a,b in zip(path,path[1:]))
                last, finished, appearances = {}, set(), set()
                for frame in range(601):
                    active = {identity:(x,y) for identity,x,y in
                              scenes.electron_positions(path, frame/600)}
                    for identity, (x,y) in active.items():
                        self.assertNotIn(identity, finished, 'A finished particle must not respawn')
                        nearest_x = max(left, min(right, x))
                        nearest_y = max(top, min(bottom, y))
                        self.assertGreater(math.dist((x,y),(nearest_x,nearest_y)),
                                           scenes.ELECTRON_RADIUS, 'Entire electron must clear insulation')
                        if identity in last:
                            self.assertLessEqual(math.dist((x,y),last[identity]),
                                                 length/(.32*600)+1e-7, 'No reset/teleport between frames')
                        appearances.add(identity)
                    finished.update(set(last)-set(active))
                    last = active
                self.assertEqual(appearances, set(range(6)))
                self.assertEqual(finished, appearances)

    def test_electron_routes_connect_external_terminals_in_the_right_direction(self):
        # Charging: upper plate -> positive supply, negative supply -> lower.
        self.assertEqual(scenes.path_point(scenes.CHARGE_OUT, 0), (520,208))
        self.assertEqual(scenes.path_point(scenes.CHARGE_OUT, 1), (180,231))
        self.assertEqual(scenes.path_point(scenes.CHARGE_IN, 0), (180,312))
        self.assertEqual(scenes.path_point(scenes.CHARGE_IN, 1), (520,328))
        # Discharge uses the external load on the right, lower -> upper plate.
        self.assertEqual(scenes.path_point(scenes.DISCHARGE, 0), (620,328))
        self.assertEqual(scenes.path_point(scenes.DISCHARGE, 1), (620,208))
        self.assertEqual(scenes.path_point(scenes.DISCHARGE, .5), (800,268))
        self.assertFalse(scenes.electron_positions(scenes.DISCHARGE, 1.1))


if __name__ == '__main__':
    unittest.main()
