"""Simulated semester: the same seed must always produce the same history and eval result."""

import app as portal
from scripts.ranking_eval import evaluate, hits_in_top
from scripts.seed_ranking_eval import seed_simulated_semester
from tests.postgres_test_support import PostgresTestCase


class SimulatedSemesterTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        with portal.get_db() as db:
            self.counts = seed_simulated_semester(db)

    def test_semester_is_the_same_every_run(self):
        self.assertEqual(self.counts, {"advisors": 21, "students": 20, "requests": 80,
                                       "accepted": 56, "reviews": 39})

    def test_eval_result_on_the_simulated_semester(self):
        # Recorded result for the current weights and starting values. If ranking
        # changes on purpose, update these numbers and the documented result together.
        with portal.get_db() as db:
            new_positions, old_positions = evaluate(db)
        self.assertEqual(len(new_positions), 56)
        self.assertEqual((hits_in_top(new_positions), hits_in_top(old_positions)), (24, 10))

    def test_seeding_twice_is_refused(self):
        with portal.get_db() as db, self.assertRaises(RuntimeError):
            seed_simulated_semester(db)
