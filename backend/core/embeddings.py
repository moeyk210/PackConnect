"""Turn short texts, like advice topics, into fingerprints for meaning-based matching.

A fingerprint ("embedding") is a list of 384 numbers from a small language
model. Texts with similar meanings get similar fingerprints, so "job hunting"
lands close to "resume reviews, career fairs" even though they share no words.
pgvector stores the fingerprints in students.topic_embedding and compares them.

The model runs on this server through fastembed: no outside service is called
and no student text leaves the server.
"""

import threading

# The model and the fingerprint size it produces. Changing the model means
# working out every stored fingerprint again (scripts/backfill_topic_embeddings.py).
MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_SIZE = 384


class TopicEmbedder:
    """Creates fingerprints with the local model.

    The model (about 65 MB) is downloaded and loaded the first time it is
    needed, not when the app starts, so tests and scripts that never embed
    anything stay fast.
    """

    def __init__(self, model_name=MODEL_NAME):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _loaded_model(self):
        with self._lock:
            if self._model is None:
                from fastembed import TextEmbedding

                self._model = TextEmbedding(self.model_name)
            return self._model

    def embed(self, texts):
        """Return one fingerprint (a list of floats) per text, in the same order."""
        return [vector.tolist() for vector in self._loaded_model().embed(list(texts))]


def vector_literal(vector):
    """Write a fingerprint the way pgvector reads it, for example "[0.12,-0.03,...]"."""
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"
