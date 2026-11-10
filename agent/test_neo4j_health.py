"""Offline tests for the Neo4j health check: every failure mode is classified and explained, and a healthy database is reported ok. Run: python3 -m unittest agent.test_neo4j_health"""
import socket
import unittest
from unittest import mock

from neo4j.exceptions import AuthError, ServiceUnavailable

from agent import neo4j_health as H

ENV = {"NEO4J_URI": "neo4j+s://abc12345.databases.neo4j.io", "NEO4J_USERNAME": "u", "NEO4J_PASSWORD": "p"}


class Driver:
    def __init__(self, exc=None):
        self.exc = exc

    def session(self):
        outer = self

        class S:
            def __enter__(self_):
                if outer.exc:
                    raise outer.exc
                return self_

            def __exit__(self_, *a):
                return False

            def run(self_, q, **k):
                return mock.Mock(consume=lambda: None, single=lambda: {"c": 5})
        return S()

    def close(self):
        pass


class TestHealth(unittest.TestCase):
    def run_check(self, env=ENV, dns_ok=True, driver=None):
        with mock.patch.dict("os.environ", env, clear=True), mock.patch.object(H, "load_dotenv"), \
                mock.patch.object(H.socket, "getaddrinfo", side_effect=None if dns_ok else socket.gaierror("no")), \
                mock.patch("neo4j.GraphDatabase.driver", return_value=driver or Driver()):
            return H.check("Live app graph", "NEO4J", counts=True)

    def test_healthy(self):
        r = self.run_check()
        self.assertEqual((r["ok"], r["state"]), (True, "ok"))
        self.assertEqual(r["nodes"], 5)

    def test_missing_configuration_is_explained(self):
        r = self.run_check(env={})
        self.assertEqual((r["ok"], r["state"]), (False, "not_configured"))
        self.assertIn("NEO4J_URI", r["hint"])

    def test_a_host_that_does_not_resolve_is_reported_as_paused_first_with_the_right_reload_command(self):
        r = self.run_check(dns_ok=False)
        self.assertEqual(r["state"], "unresolved")
        self.assertIn("PAUSED", r["hint"])                      # a paused Aura Free instance stops resolving; its data is kept
        self.assertIn("neo4j_loader.py", r["hint"])             # ...and only a long-paused (deleted) instance needs the reload
        with mock.patch.dict("os.environ", {**{k.replace("NEO4J", "NEO4J_V2"): v for k, v in ENV.items()}}, clear=True), mock.patch.object(H, "load_dotenv"), \
                mock.patch.object(H.socket, "getaddrinfo", side_effect=socket.gaierror("no")):
            self.assertIn("build_graph", H.check("Phase 4 agent graph", "NEO4J_V2")["hint"])

    def test_wrong_password_and_paused_instance_are_distinguished(self):
        self.assertEqual(self.run_check(driver=Driver(AuthError("bad"))).get("state"), "auth")
        r = self.run_check(driver=Driver(ServiceUnavailable("down")))
        self.assertEqual(r["state"], "paused")
        self.assertIn("resume", r["hint"])

    def test_check_never_writes(self):
        import inspect
        src = inspect.getsource(H.check)
        for w in ("CREATE", "MERGE", "DELETE", "SET "):
            self.assertNotIn(w, src)


if __name__ == "__main__":
    unittest.main()
