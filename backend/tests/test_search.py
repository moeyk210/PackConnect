"""Search behavior against independent fictional profiles in PostgreSQL."""

import app as portal
from tests.postgres_test_support import PostgresTestCase, sign_in


class SearchFixture(PostgresTestCase):
    """Fictional profiles shared by the search tests below."""

    def setUp(self):
        super().setUp()
        self.client = portal.app.test_client()
        self.ids = {}
        # Deliberate near-matches catch filters that are ignored or ORed together.
        profiles = [
            ("Ada", "Computer Science", "Second Year", "Python, SQL", "Projects", True, "CSC 510"),
            ("Blake", "Computer Science", "First Year", "Java", "Projects", True, "CSC 510"),
            ("Casey", "Statistics", "Second Year", "Python", "Workload", True, "CSC 510"),
            ("Dev", "Computer Science", "Second Year", "Python", "Projects", False, "CSC 510"),
            ("Eli", "Computer Science", "Second Year", "Python", "Projects", True, "CSC 540"),
            ("Faye", "Computer Science", "Second Year", "Python", "Workload", True, "CSC 510"),
        ]
        with portal.get_db() as db:
            db.execute("DELETE FROM accounts")
            db.execute("DELETE FROM completed_courses")
            db.execute("DELETE FROM students")
            for name, program, year, skills, topics, willing, course in profiles:
                student_id = db.execute("""
                    INSERT INTO students (name, program, year, skills, advice_topics, willing_to_advise)
                    VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                """, (name, program, year, skills, topics, willing)).fetchone()["id"]
                self.ids[name] = student_id
                db.execute("""
                    INSERT INTO accounts (student_id, email, password_hash)
                    VALUES (%s, %s, %s)
                """, (student_id, f"{name.lower()}@example.test", "unused-test-hash"))
                db.execute("INSERT INTO completed_courses (student_id, course_code) VALUES (%s, %s)",
                           (student_id, course))
            db.execute("INSERT INTO current_courses (student_id, course_code) VALUES (%s, 'CSC 510')",
                       (self.ids["Eli"],))

    def search(self, **filters):
        response = self.client.get("/api/students/search", query_string=filters)
        self.assertEqual(response.status_code, 200)
        return response.get_json()["students"]

    def assert_matches(self, expected, **filters):
        rows = self.search(**filters)
        self.assertEqual([row["name"] for row in rows], sorted(expected))
        self.assertEqual([row["id"] for row in rows], [self.ids[name] for name in sorted(expected)])
        return rows


class SearchTests(SearchFixture):
    def test_course_search_normalizes_case_and_outer_whitespace(self):
        for course in ("CSC 510", "csc 510", "  CsC 510  ", "CSC510", "csc-510", "CSC   510"):
            with self.subTest(course=course):
                self.assert_matches(["Ada", "Blake", "Casey", "Faye"], course=course)

    def test_course_suggestions_normalize_deduplicate_and_match_prefixes(self):
        with portal.get_db() as db:
            db.execute("INSERT INTO completed_courses (student_id, course_code) VALUES (%s, 'csc-510')",
                       (self.ids["Ada"],))
        for query in ("csc", " CSC ", "csc5", "CSC-5"):
            response = self.client.get('/api/courses', query_string={"q": query})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json(), {"courses": ["CSC 510", "CSC 540"]})
        self.assert_matches(["Ada", "Blake", "Casey", "Faye"], course="CSC510")

    def test_course_suggestions_only_include_registered_completed_courses(self):
        with portal.get_db() as db:
            db.execute("DELETE FROM accounts WHERE student_id = %s", (self.ids["Eli"],))
            db.execute("INSERT INTO current_courses (student_id, course_code) VALUES (%s, 'CSC 555')",
                       (self.ids["Ada"],))
        self.assertEqual(self.client.get('/api/courses?q=CSC').get_json(), {"courses": ["CSC 510"]})

    def test_suggested_code_finds_legacy_course_format_and_updates_with_profile(self):
        with portal.get_db() as db:
            db.execute("UPDATE completed_courses SET course_code = ' ece- 570 ' WHERE student_id = %s",
                       (self.ids["Eli"],))
        suggestion = self.client.get('/api/courses?q=ece5').get_json()["courses"]
        self.assertEqual(suggestion, ["ECE 570"])
        self.assert_matches(["Eli"], course=suggestion[0])
        sign_in(self.client, self.ids["Eli"])
        response = self.client.put(f'/api/students/{self.ids["Eli"]}', json={
            "name": "Eli", "program": "Computer Science", "year": "Second Year",
            "completed_courses": ["ECE 571"], "willing_to_advise": True,
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self.client.get('/api/courses?q=ECE').get_json(), {"courses": ["ECE 571"]})
        self.assert_matches([], course="ECE 570")
        self.assert_matches(["Eli"], course="ECE571")

    def test_course_suggestions_bound_results_and_treat_query_as_literal(self):
        with portal.get_db() as db:
            for number in range(600, 620):
                db.execute("INSERT INTO completed_courses (student_id, course_code) VALUES (%s, %s)",
                           (self.ids["Ada"], f"CSC {number}"))
        courses = self.client.get('/api/courses?q=CSC6').get_json()["courses"]
        self.assertEqual(courses, [f"CSC {n}" for n in range(600, 610)])
        for query in ('', ' ', '%', '_', "' OR 1=1 --", 'C' * 31, 'NONEXISTENT'):
            self.assertEqual(self.client.get('/api/courses', query_string={"q": query}).get_json(),
                             {"courses": []})

    def test_profiles_without_accounts_are_excluded_from_search(self):
        with portal.get_db() as db:
            db.execute("DELETE FROM accounts WHERE student_id = %s", (self.ids["Ada"],))
        for available in ("true", "false"):
            with self.subTest(available=available):
                rows = self.search(course="CSC 510", available=available)
                self.assertNotIn(self.ids["Ada"], [row["id"] for row in rows])
                self.assertIn(self.ids["Blake"], [row["id"] for row in rows])
        profile = self.client.get(f"/api/students/{self.ids['Ada']}").get_json()["student"]
        self.assertFalse(profile["can_receive_requests"])
        self.assertEqual(profile["completed_courses"], ["CSC 510"])

    def test_current_course_does_not_count_as_completed(self):
        self.assert_matches(["Ada", "Blake", "Casey", "Faye"], course="CSC 510", program="", available="true")
        self.assert_matches(["Eli"], course="CSC 540")

    def test_program_filter_without_course(self):
        self.assert_matches(["Ada", "Blake", "Eli", "Faye"], program="  COMPUTER  ")

    def test_year_filter_without_course(self):
        self.assert_matches(["Ada", "Casey", "Eli", "Faye"], year=" second ")

    def test_skills_filter_without_course(self):
        self.assert_matches(["Ada", "Casey", "Eli", "Faye"], skills=" pYtHoN ")

    def test_advice_topic_filter_without_course(self):
        self.assert_matches(["Ada", "Blake", "Eli"], advice_topics=" project ")

    def test_combined_filters_must_all_match(self):
        self.assert_matches(["Ada"], course="csc 510", program="computer", year="second",
                            skills="python", advice_topics="projects")
        self.assert_matches([], course="CSC 510", program="Statistics", advice_topics="Projects")

    def test_availability_defaults_to_opted_in_profiles(self):
        for available in (None, "true", " TRUE "):
            with self.subTest(available=available):
                filters = {} if available is None else {"available": available}
                rows = self.assert_matches(["Ada", "Blake", "Casey", "Faye"], course="CSC 510", **filters)
                self.assertTrue(all(row["willing_to_advise"] is True for row in rows))

    def test_available_false_includes_opted_out_profiles(self):
        rows = self.assert_matches(["Ada", "Blake", "Casey", "Dev", "Faye"],
                                   course="CSC 510", available=" FALSE ")
        self.assertIs(next(row for row in rows if row["name"] == "Dev")["willing_to_advise"], False)

    def test_empty_or_whitespace_search_does_not_list_everyone(self):
        for filters in ({}, {"course": "  "}, {"available": "false"},
                        {"course": " ", "program": " ", "year": " ", "skills": " ", "advice_topics": " "}):
            with self.subTest(filters=filters):
                self.assertEqual(self.search(**filters), [])

    def test_unknown_filter_values_return_no_matches(self):
        for field in ("course", "program", "year", "skills", "advice_topics"):
            with self.subTest(field=field):
                self.assertEqual(self.search(**{field: "NONEXISTENT 999"}), [])

    def test_repeated_course_records_do_not_duplicate_results(self):
        with portal.get_db() as db:
            db.execute("INSERT INTO completed_courses (student_id, course_code) VALUES (%s, 'CSC 510')",
                       (self.ids["Ada"],))
        self.assert_matches(["Ada", "Blake", "Casey", "Faye"], course="CSC 510")

    def test_search_values_cannot_bypass_filters_with_sql(self):
        for field in ("course", "program", "year", "skills", "advice_topics"):
            with self.subTest(field=field):
                self.assertEqual(self.search(**{field: "' OR 1=1 --"}), [])

    def test_search_returns_only_public_summary_fields(self):
        rows = self.search(course="CSC 510")
        self.assertTrue(rows)
        expected = {"id", "name", "program", "year", "skills", "advice_topics", "willing_to_advise", "max_open_requests", "pause_until",
                    "open_request_count", "availability_status", "accepting_requests", "reputation",
                    "score", "match_reasons", "missed_filters"}
        for row in rows:
            self.assertEqual(set(row), expected)


class RankedSearchTests(SearchFixture):
    """Ranking, the outside-your-filters group and paging, on the same fictional profiles.

    CSC 510: Ada, Blake, Casey, Faye (advising) and Dev (not advising).
    CSC 540: Eli. No one has ratings, so order comes from fit and responsiveness.
    """

    def response(self, **params):
        response = self.client.get("/api/students/search", query_string=params)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def names(self, rows):
        return [row["name"] for row in rows]

    def test_unresponsive_advisor_ranks_below_others_instead_of_alphabetically(self):
        with portal.get_db() as db:
            for sender in ("Blake", "Casey", "Eli"):
                db.execute("""
                    INSERT INTO advice_requests (sender_id, recipient_id, course_code, advice_topic, message, status)
                    VALUES (%s, %s, 'CSC 510', 'Projects', 'Can you help?', 'expired')
                """, (self.ids[sender], self.ids["Ada"]))
        self.assertEqual(self.names(self.response(course="CSC 510")["students"]), ["Blake", "Casey", "Faye", "Ada"])

    def test_near_misses_are_listed_outside_the_filters(self):
        data = self.response(course="CSC 510", program="Statistics")
        self.assertEqual(self.names(data["students"]), ["Casey"])
        self.assertEqual(self.names(data["outside_filters"]), ["Ada", "Blake", "Faye"])
        self.assertTrue(all(row["missed_filters"] == ["program"] for row in data["outside_filters"]))

    def test_fewer_missed_filters_rank_higher_outside_the_filters(self):
        data = self.response(course="CSC 510", program="Computer", year="Second", advice_topics="Workload")
        self.assertEqual(self.names(data["students"]), ["Faye"])
        # Casey and Ada each miss one filter; Casey's topic matches, so she fits better.
        # Blake misses two. Eli took CSC 540, so he comes after everyone who took CSC 510.
        self.assertEqual(self.names(data["outside_filters"]), ["Casey", "Ada", "Blake", "Eli"])

    def test_other_courses_in_the_subject_come_after_the_searched_course(self):
        data = self.response(course="CSC 510")
        self.assertEqual(self.names(data["students"]), ["Ada", "Blake", "Casey", "Faye"])
        self.assertEqual(self.names(data["outside_filters"]), ["Eli"])
        self.assertEqual(data["outside_filters"][0]["match_reasons"], ["Took CSC 540", "No reviews yet"])

    def test_other_subjects_never_appear(self):
        data = self.response(course="MA 101")
        self.assertEqual((data["students"], data["outside_filters"]), ([], []))

    def test_pages_move_through_matches_and_keep_near_misses_fixed(self):
        everyone = self.response(course="CSC 510")
        pages = [self.response(course="CSC 510", limit=2, offset=offset) for offset in (0, 2)]
        paged = [name for page in pages for name in self.names(page["students"])]
        self.assertEqual(paged, self.names(everyone["students"]))
        self.assertTrue(all(self.names(page["outside_filters"]) == ["Eli"] for page in pages))
        self.assertEqual((pages[0]["total_matches"], pages[0]["total_outside_filters"]), (4, 1))

    def test_invalid_paging_is_rejected(self):
        for params in ({"limit": "abc"}, {"limit": "0"}, {"offset": "-1"}):
            with self.subTest(params=params):
                response = self.client.get("/api/students/search", query_string={"course": "CSC 510", **params})
                self.assertEqual(response.status_code, 400)

    def test_unchecking_no_reviews_hides_unrated_advisors(self):
        data = self.response(course="CSC 510", include_unrated="false")
        self.assertEqual((data["students"], data["outside_filters"]), ([], []))
