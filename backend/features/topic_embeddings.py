"""Fingerprints of advice topics, stored on each student for meaning-based matching.

See core/embeddings.py for what a fingerprint is. This module decides when a
fingerprint is made and what happens when the model cannot run: matching then
falls back to shared words, so a model problem never blocks saving a profile.
"""

import logging

from core.embeddings import vector_literal

logger = logging.getLogger(__name__)


def topic_embedding_value(embedder, advice_topics):
    """Return what to store in students.topic_embedding for these topics.

    That is a fingerprint written for pgvector, or None when there are no topics
    or the model is unavailable.
    """
    text = (advice_topics or "").strip()
    if not text:
        return None
    try:
        return vector_literal(embedder.embed([text])[0])
    except Exception:
        # Topic text is the student's own writing, so it is not logged.
        logger.warning("Could not create a topic fingerprint; matching will use shared words only.")
        return None
