"""Topic fingerprints: formatting, lazy model loading, and (on request) the real model."""

import math
import os
import sys
import types
import unittest
from unittest.mock import patch

from core.embeddings import EMBEDDING_SIZE, TopicEmbedder, vector_literal


def cosine(first, second):
    dot = sum(a * b for a, b in zip(first, second))
    return dot / (math.sqrt(sum(a * a for a in first)) * math.sqrt(sum(b * b for b in second)))


class VectorLiteralTests(unittest.TestCase):
    def test_writes_the_format_pgvector_reads(self):
        self.assertEqual(vector_literal([0.5, -0.25, 1]), "[0.500000,-0.250000,1.000000]")


class LazyLoadingTests(unittest.TestCase):
    def test_model_loads_on_first_use_and_only_once(self):
        loads = []

        class StubModel:
            def __init__(self, name):
                loads.append(name)

            def embed(self, texts):
                return [types.SimpleNamespace(tolist=lambda: [1.0, 0.0]) for _ in texts]

        stub_module = types.SimpleNamespace(TextEmbedding=StubModel)
        with patch.dict(sys.modules, {"fastembed": stub_module}):
            embedder = TopicEmbedder("stub-model")
            self.assertEqual(loads, [])
            self.assertEqual(embedder.embed(["a", "b"]), [[1.0, 0.0], [1.0, 0.0]])
            embedder.embed(["c"])
        self.assertEqual(loads, ["stub-model"])


@unittest.skipUnless(os.getenv("RUN_EMBEDDING_MODEL") == "1", "set RUN_EMBEDDING_MODEL=1 to load the real model")
class RealModelTests(unittest.TestCase):
    def test_related_topics_are_closer_than_unrelated_ones(self):
        need, related, unrelated = TopicEmbedder().embed(
            ["interview prep", "Projects, interviews", "Course workload"])
        self.assertEqual(len(need), EMBEDDING_SIZE)
        self.assertGreater(cosine(need, related), cosine(need, unrelated))


if __name__ == "__main__":
    unittest.main()
