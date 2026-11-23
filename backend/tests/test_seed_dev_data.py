"""Search, filters, availability, recommendations, course pages and request flows
on the varied development seed (scripts/seed_dev_data.py).

Each expected list below was worked out by hand from the seed's people and
history, so a change in search or ranking behavior shows up as a failure here.
"""

import io
from contextlib import redirect_stdout
from unittest import TestCase

import app as portal
from core.courses import normalize_code
from import_catalog import import_catalog
from scripts import seed_dev_data as seed_module
from scripts.backfill_topic_embeddings import backfill_topic_embeddings
from scripts.seed_dev_data import (ADVISORS, DEV_DOMAIN, DEV_PASSWORD, EXPECTED_COUNTS, HISTORY, STUDENTS,
                                   seed_dev_data)
from tests.postgres_test_support import PostgresTestCase, sign_in

# Available advisors who completed CSC 510, best fit first. Liam (paused), Chen
# (not advising) and Robin (no account) also took it but must never be listed.
CSC_510_ORDER = ["Ava Thompson", "Lena Park", "Amara Okeke", "Diego Alvarez", "Isabela Costa",
                 "Tariq Mensah", "Zoe Martin", "Jonas Weber"]


def names(rows):
    return [row["name"] for row in rows]


class DevSeedTestCase(PostgresTestCase):
    """Seeds the development data, with topic fingerprints from the tests' stand-in model."""

    def setUp(self):
        super().setUp()
        with portal.get_db() as db:
            self.ids = seed_dev_data(db)
            backfill_topic_embeddings(db, portal.app.config["TOPIC_EMBEDDER"])
        self.client = portal.app.test_client()

    def search(self, client=None, **query):
        response = (client or self.client).get("/api/students/search", query_string=query)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def signed_in(self, key):
        client = portal.app.test_client()
        sign_in(client, self.ids[key])
        return client

    def request_advice(self, sender, recipient, course="CSC 216"):
        return self.signed_in(sender).post("/api/requests", json={
            "recipient_id": self.ids[recipient], "course_code": course,
            "advice_topic": "Projects", "message": "Could you help me get started?"})


class SeedContentsTests(DevSeedTestCase):
    def test_counts_match_the_documented_totals(self):
        with portal.get_db() as db:
            accounts = db.execute("SELECT count(*) FROM accounts WHERE email LIKE %s",
                                  (f"%@{DEV_DOMAIN}",)).fetchone()["count"]
            requests = db.execute("SELECT count(*) FROM advice_requests").fetchone()["count"]
            reviews = db.execute("SELECT count(*) FROM advice_feedback").fetchone()["count"]
        self.assertEqual(accounts, EXPECTED_COUNTS["advisors"] + EXPECTED_COUNTS["students"])
        self.assertEqual((requests, reviews), (EXPECTED_COUNTS["requests"], EXPECTED_COUNTS["reviews"]))

    def test_seeding_twice_is_refused(self):
        with portal.get_db() as db, self.assertRaisesRegex(RuntimeError, "already present"):
            seed_dev_data(db)

    def test_advisors_and_students_can_sign_in(self):
        for key in ("ava", "riley"):
            with self.subTest(key=key):
                response = portal.app.test_client().post("/api/auth/login", json={
                    "email": f"{key}@{DEV_DOMAIN}", "password": DEV_PASSWORD})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["student"]["id"], self.ids[key])

    def test_every_advisor_has_courses_and_every_course_code_is_canonical(self):
        for key, person in {**ADVISORS, **STUDENTS}.items():
            with self.subTest(key=key):
                for course in person.completed + person.current:
                    self.assertEqual(normalize_code(course), course)
                if key in ADVISORS:
                    self.assertTrue(person.completed)

    def test_every_csc_course_used_is_in_the_catalog(self):
        with portal.get_db() as db:
            import_catalog(db)
            catalog = {row["code"] for row in db.execute("SELECT code FROM courses")}
        used = {course for person in {**ADVISORS, **STUDENTS}.values() for course in person.completed + person.current}
        used |= {course for _, _, course, *_ in HISTORY}
        self.assertEqual({course for course in used if course.startswith("CSC ")} - catalog, set())

    def test_people_have_varied_programs_years_and_topics(self):
        advisors = ADVISORS.values()
        self.assertGreaterEqual(len({person.program for person in advisors}), 5)
        self.assertGreaterEqual(len({person.year for person in advisors}), 5)
        self.assertGreaterEqual(len({course.split()[0] for person in advisors for course in person.completed}), 4)
        self.assertGreaterEqual(len({course for person in advisors for course in person.completed}), 25)


class CourseSearchTests(DevSeedTestCase):
    def test_csc_510_lists_available_advisors_best_fit_first(self):
        result = self.search(course="CSC 510")
        self.assertEqual(names(result["students"]), CSC_510_ORDER)
        self.assertEqual(result["total_matches"], len(CSC_510_ORDER))

    def test_every_spelling_of_a_course_gives_the_same_results(self):
        expected = names(self.search(course="CSC 510")["students"])
        for spelling in ("csc510", "CSC-510", "  csc   510 ", "Csc 510"):
            with self.subTest(spelling=spelling):
                self.assertEqual(names(self.search(course=spelling)["students"]), expected)

    def test_unavailable_advisors_appear_only_when_asked_for(self):
        everyone = names(self.search(course="CSC 510", available="false")["students"])
        # Turning availability off also lists registered students who completed
        # the course but do not advise (Alex, Jamie and Jordan), as documented.
        self.assertEqual(set(everyone) - set(CSC_510_ORDER),
                         {"Liam O'Brien", "Chen Wu", "Alex Romero", "Jamie Lee", "Jordan Ellis"})
        self.assertNotIn("Robin Hayes", everyone)

    def test_an_advisor_with_several_courses_is_found_for_each(self):
        for course in ADVISORS["ava"].completed:
            with self.subTest(course=course):
                self.assertIn("Ava Thompson", names(self.search(course=course)["students"]))

    def test_current_courses_do_not_count_as_completed(self):
        # Isabela is taking CSC 522 now; only those who finished it are matches.
        self.assertEqual(names(self.search(course="CSC 522")["students"]), ["Omar Haddad", "Nora Lindqvist"])

    def test_other_csc_advisors_are_near_misses_and_other_subjects_never_appear(self):
        result = self.search(course="CSC 510")
        outside = names(result["outside_filters"])
        self.assertEqual(result["total_outside_filters"], 11)
        self.assertIn("Hannah Schmidt", outside)
        self.assertIn("Mateo Silva", outside)
        self.assertTrue(all(row["match_reasons"][0].startswith("Took CSC ") for row in result["outside_filters"]))
        self.assertNotIn("Fatima Diallo", outside)

    def test_non_csc_subjects_only_show_their_own_subject(self):
        for course, expected in (("MA 305", ["Hannah Schmidt"]), ("ECE 306", ["Mateo Silva"]),
                                 ("ST 512", ["Nora Lindqvist"])):
            with self.subTest(course=course):
                result = self.search(course=course)
                self.assertEqual(names(result["students"]), expected)
                self.assertEqual(result["outside_filters"], [])

    def test_a_course_nobody_took_still_offers_the_same_subject(self):
        result = self.search(course="CSC 999")
        self.assertEqual(result["students"], [])
        self.assertEqual(result["total_outside_filters"], 19)

    def test_an_unknown_subject_finds_nobody(self):
        result = self.search(course="XYZ 100")
        self.assertEqual((result["students"], result["outside_filters"]), ([], []))

    def test_ties_are_broken_by_name_including_accented_names(self):
        self.assertEqual(names(self.search(course="CSC 501")["students"]), ["Noémie Dubois", "Wei Zhang"])

    def test_pages_split_the_matches_without_overlap(self):
        first = self.search(course="CSC 510", limit=3)
        second = self.search(course="CSC 510", limit=3, offset=3)
        last = self.search(course="CSC 510", limit=3, offset=6)
        self.assertEqual(names(first["students"] + second["students"] + last["students"]), CSC_510_ORDER)
        self.assertEqual(first["outside_filters"], last["outside_filters"])


class FilterTests(DevSeedTestCase):
    def test_program_filter_alone(self):
        self.assertEqual(names(self.search(program="statistics")["students"]), ["Nora Lindqvist"])
        self.assertEqual(set(names(self.search(program="Computer Engineering")["students"])),
                         {"Diego Alvarez", "Mateo Silva"})

    def test_year_filter_alone(self):
        self.assertEqual(set(names(self.search(year="senior")["students"])),
                         {"Marcus Bell", "Hannah Schmidt", "Mateo Silva"})
        self.assertEqual(names(self.search(year="Third")["students"]), ["Omar Haddad"])

    def test_skills_filter_ignores_case_and_matches_part_of_the_list(self):
        self.assertEqual(set(names(self.search(skills="PYTHON")["students"])),
                         {"Ava Thompson", "Omar Haddad", "Tariq Mensah", "Zoe Martin", "Jonas Weber"})
        self.assertEqual(names(self.search(skills="docker")["students"]), ["Diego Alvarez"])

    def test_skills_with_symbols_are_matched_literally(self):
        self.assertEqual(names(self.search(skills="C#")["students"]), ["Isabela Costa"])
        self.assertEqual(names(self.search(skills="C++")["students"]), ["Wei Zhang"])

    def test_topic_filter_on_a_course_keeps_misses_below_the_matches(self):
        result = self.search(course="CSC 510", advice_topics="interview prep")
        self.assertEqual(names(result["students"]), ["Lena Park", "Zoe Martin"])
        self.assertTrue(all(row["missed_filters"] == ["advice_topics"] for row in result["outside_filters"]))
        self.assertEqual(set(names(result["outside_filters"])),
                         set(CSC_510_ORDER) - {"Lena Park", "Zoe Martin"})

    def test_matching_topic_words_are_explained(self):
        lena = self.search(course="CSC 510", advice_topics="interview prep")["students"][0]
        self.assertEqual(lena["match_reasons"][0], "Advises on interview prep")

    def test_a_partly_matching_topic_is_a_near_miss_that_names_the_shared_word(self):
        result = self.search(course="CSC 510", advice_topics="interview tips")
        self.assertNotIn("Lena Park", names(result["students"]))
        lena = next(row for row in result["outside_filters"] if row["name"] == "Lena Park")
        self.assertEqual(lena["match_reasons"][0], "Advises on interview")

    def test_every_filter_combined_must_match(self):
        result = self.search(course="CSC 510", program="computer science", year="second",
                             skills="python", advice_topics="projects")
        self.assertEqual(names(result["students"]), ["Ava Thompson", "Jonas Weber"])

    def test_contradictory_filters_find_no_matches(self):
        self.assertEqual(self.search(course="CSC 510", program="Statistics", year="Freshman")["students"], [])

    def test_students_who_are_not_advising_appear_only_when_availability_is_off(self):
        # Drew is in MS Statistics but does not advise.
        self.assertNotIn("Drew Kim", names(self.search(program="statistics")["students"]))
        self.assertIn("Drew Kim", names(self.search(program="statistics", available="false")["students"]))


class AvailabilityTests(DevSeedTestCase):
    def profile(self, key):
        return self.client.get(f"/api/students/{self.ids[key]}").get_json()["student"]

    def test_each_availability_state_is_reported_on_the_profile(self):
        expected = {"ava": "available", "isabela": "available", "liam": "paused",
                    "fatima": "at_capacity", "chen": "not_advising", "robin": "unregistered"}
        for key, status in expected.items():
            with self.subTest(key=key):
                self.assertEqual(self.profile(key)["availability_status"], status)

    def test_unlimited_and_limited_advisors(self):
        self.assertIsNone(self.profile("isabela")["max_open_requests"])
        fatima = self.profile("fatima")
        self.assertEqual((fatima["max_open_requests"], fatima["open_request_count"]), (1, 1))

    def test_paused_advisor_rejects_requests_with_the_date(self):
        response = self.request_advice("riley", "liam", "CSC 510")
        self.assertEqual(response.status_code, 409)
        self.assertIn("paused new requests until", response.get_json()["error"])

    def test_full_advisor_rejects_requests(self):
        response = self.request_advice("riley", "fatima")
        self.assertEqual(response.status_code, 409)
        self.assertIn("open-request limit", response.get_json()["error"])

    def test_not_advising_and_unregistered_profiles_reject_requests(self):
        for key in ("chen", "robin"):
            with self.subTest(key=key):
                self.assertEqual(self.request_advice("riley", key, "CSC 510").status_code, 400)

    def test_full_advisor_reopens_when_the_connection_completes(self):
        with portal.get_db() as db:
            db.execute("UPDATE advice_requests SET status = 'completed' WHERE recipient_id = %s", (self.ids["fatima"],))
        self.assertIn("Fatima Diallo", names(self.search(course="CSC 316")["students"]))
        self.assertEqual(self.request_advice("riley", "fatima").status_code, 201)


class ReputationTests(DevSeedTestCase):
    def reputation(self, key):
        return self.client.get(f"/api/students/{self.ids[key]}/reputation").get_json()["reputation"]

    def test_stats_for_a_well_reviewed_advisor(self):
        self.assertEqual(self.reputation("ava"), {"average_rating": 9.5, "rating_count": 4, "helpful_percent": 100,
                                                  "students_helped": 4, "response_rate": 100})

    def test_stats_for_an_advisor_who_never_answers(self):
        self.assertEqual(self.reputation("jonas"), {"average_rating": None, "rating_count": 0,
                                                    "helpful_percent": None, "students_helped": 0,
                                                    "response_rate": 0})

    def test_declines_count_as_answered(self):
        self.assertEqual(self.reputation("marcus")["response_rate"], 100)
        self.assertEqual(self.reputation("marcus")["students_helped"], 2)

    def test_reasons_describe_reviews_and_responses(self):
        rows = {row["name"]: row for row in self.search(course="CSC 510")["students"]}
        self.assertEqual(rows["Ava Thompson"]["match_reasons"], ["9.5/10 (4 reviews)", "Answers 100% of requests"])
        self.assertEqual(rows["Jonas Weber"]["match_reasons"], ["No reviews yet", "Answers 0% of requests"])
        # A brand-new advisor shows no made-up response rate.
        self.assertEqual(rows["Tariq Mensah"]["match_reasons"], ["No reviews yet"])

    def test_poor_reviews_rank_below_advisors_with_no_reviews(self):
        order = CSC_510_ORDER
        self.assertLess(order.index("Tariq Mensah"), order.index("Zoe Martin"))
        self.assertEqual(order[-1], "Jonas Weber")

    def test_hiding_unreviewed_advisors(self):
        self.assertEqual(names(self.search(course="CSC 510", include_unrated="false")["students"]),
                         ["Ava Thompson", "Lena Park", "Zoe Martin"])


class RecommendationTests(DevSeedTestCase):
    def recommended(self, key):
        response = self.signed_in(key).get("/api/recommendations")
        self.assertEqual(response.status_code, 200)
        return response.get_json()["students"]

    def test_past_connections_are_left_out_and_the_list_is_capped(self):
        # Sam already has history with Ava, Lena, Zoe and Sofia.
        self.assertEqual(names(self.recommended("sam")),
                         ["Amara Okeke", "Diego Alvarez", "Isabela Costa", "Tariq Mensah", "Jonas Weber"])

    def test_no_current_courses_means_no_recommendations(self):
        self.assertEqual(self.recommended("jordan"), [])

    def test_blocked_and_full_advisors_are_left_out(self):
        # Taylor blocked Kenji, and Fatima is full; both took Taylor's current courses.
        self.assertEqual(names(self.recommended("taylor")), ["Ava Thompson", "Marcus Bell"])

    def test_current_course_without_completion_does_not_qualify(self):
        # Isabela is only taking CSC 522, so she is not recommended for it.
        self.assertEqual(names(self.recommended("drew")), ["Omar Haddad", "Nora Lindqvist"])

    def test_reasons_name_the_matching_current_course(self):
        aarav = self.recommended("casey")
        self.assertEqual(names(aarav), ["Aarav Shah"])
        self.assertEqual(aarav[0]["match_reasons"][0], "Took CSC 116")


class BlockingTests(DevSeedTestCase):
    def test_blocked_advisor_is_hidden_only_from_the_people_involved(self):
        self.assertNotIn("Kenji Watanabe", names(self.search(self.signed_in("taylor"), course="CSC 230")["students"]))
        self.assertIn("Kenji Watanabe", names(self.search(self.signed_in("riley"), course="CSC 230")["students"]))
        self.assertIn("Kenji Watanabe", names(self.search(course="CSC 230")["students"]))

    def test_blocked_pair_cannot_send_requests_either_way(self):
        self.assertEqual(self.request_advice("taylor", "kenji", "CSC 230").status_code, 403)
        self.assertEqual(self.request_advice("kenji", "taylor", "CSC 230").status_code, 403)


class CatalogTests(DevSeedTestCase):
    def setUp(self):
        super().setUp()
        with portal.get_db() as db:
            import_catalog(db)

    def page(self, code, client=None):
        return (client or self.client).get(f"/api/courses/{code}")

    def test_course_page_ranks_advisors_by_smoothed_rating(self):
        body = self.page("CSC 510").get_json()
        self.assertEqual(body["course"]["title"], "Software Engineering")
        self.assertEqual(names(body["advisors"]), ["Ava Thompson", "Lena Park", "Zoe Martin", "Amara Okeke",
                                                   "Diego Alvarez", "Isabela Costa", "Jonas Weber", "Tariq Mensah"])

    def test_course_ratings_show_once_three_students_rated(self):
        # Alex rated two CSC 510 conversations but counts once (workload 3, difficulty 4.5).
        ratings = self.page("CSC 510").get_json()["ratings"]
        self.assertEqual(ratings["workload"], {"average": 3.7, "count": 3})
        self.assertEqual(ratings["difficulty"], {"average": 3.8, "count": 3})

    def test_course_ratings_stay_hidden_with_two_raters(self):
        ratings = self.page("CSC 316").get_json()["ratings"]
        self.assertEqual((ratings["workload"], ratings["difficulty"]), (None, None))

    def test_courses_outside_the_catalog_have_no_page(self):
        self.assertEqual(self.page("MA 305").status_code, 404)

    def test_signed_in_advisor_is_not_listed_on_their_own_course(self):
        advisors = self.page("CSC 510", self.signed_in("ava")).get_json()["advisors"]
        self.assertNotIn("Ava Thompson", names(advisors))

    def test_autocomplete_by_title_and_by_code(self):
        by_title = {row["code"] for row in self.client.get("/api/courses?q=software").get_json()["courses"]}
        self.assertLessEqual({"CSC 216", "CSC 326", "CSC 510", "CSC 515"}, by_title)
        by_code = [row["code"] for row in self.client.get("/api/courses?q=csc51").get_json()["courses"]]
        self.assertTrue(by_code)
        self.assertTrue(all(code.startswith("CSC 51") for code in by_code))


class RequestFlowTests(DevSeedTestCase):
    def test_find_request_accept_chat_rate_and_see_the_new_rating(self):
        riley, aarav = self.signed_in("riley"), self.signed_in("aarav")
        found = names(self.search(riley, course="CSC 216")["students"])
        self.assertEqual(found, ["Marcus Bell", "Aarav Shah"])

        request_id = self.request_advice("riley", "aarav").get_json()["request"]["id"]
        self.assertEqual(aarav.patch(f"/api/requests/{request_id}", json={"status": "accepted"}).status_code, 200)
        for client, body in ((riley, "Hi! How did you study?"), (aarav, "Weekly practice problems.")):
            self.assertEqual(client.post(f"/api/requests/{request_id}/messages", json={"body": body}).status_code, 201)
        response = riley.post(f"/api/requests/{request_id}/feedback", json={"rating": 9, "helpful": True})
        self.assertEqual(response.status_code, 201)

        aarav_row = next(row for row in self.search(course="CSC 216")["students"] if row["name"] == "Aarav Shah")
        self.assertEqual(aarav_row["match_reasons"], ["9.0/10 (1 review)", "Answers 100% of requests"])

    def test_a_second_request_to_the_same_advisor_waits_for_the_first(self):
        # Alex already has a pending request with Diego.
        response = self.request_advice("alex", "diego", "CSC 547")
        self.assertEqual(response.status_code, 409)

    def test_a_declined_pair_may_try_again(self):
        self.assertEqual(self.request_advice("riley", "marcus").status_code, 201)

    def test_students_cannot_request_advice_from_themselves(self):
        self.assertEqual(self.request_advice("aarav", "aarav").status_code, 400)

    def test_requests_store_the_canonical_course_code(self):
        response = self.request_advice("riley", "aarav", "csc-216")
        self.assertEqual(response.get_json()["request"]["course_code"], "CSC 216")


class CommandLineTests(TestCase):
    def test_non_local_databases_are_refused(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = seed_module.main(["--database-url", "postgresql://u:p@db.example.com/postgres"])
        self.assertEqual(status, 2)
        self.assertIn("Refusing", output.getvalue())
