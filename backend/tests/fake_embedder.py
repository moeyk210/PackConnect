"""A stand-in for the language model, so tests never download or load it.

Each word is hashed to one of the 384 positions, so texts that share words get
similar fingerprints and texts with no words in common get unrelated ones. It
does not understand meaning; tests that need real meaning use the real model
and only run when RUN_EMBEDDING_MODEL=1.
"""

import hashlib
import math
import re

from core.embeddings import EMBEDDING_SIZE


class FakeEmbedder:
    def __init__(self):
        self.calls = []

    def embed(self, texts):
        texts = list(texts)
        self.calls.append(texts)
        return [self._fingerprint(text) for text in texts]

    @staticmethod
    def _fingerprint(text):
        vector = [0.0] * EMBEDDING_SIZE
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            position = int(hashlib.sha256(word.rstrip("s").encode()).hexdigest(), 16) % EMBEDDING_SIZE
            vector[position] += 1.0
        length = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / length for value in vector]
