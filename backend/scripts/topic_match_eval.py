"""Topic matching eval for issue #3: does meaning-based matching find the right advisor?

    python backend/scripts/topic_match_eval.py

For each hand-written case in scripts/topic_match_cases.py, every advisor topic
list is scored against what the student asked for, using the same topic rules
as search. A case counts as a hit when the right advisor scores strictly
highest (a tie for first is not a hit). Shared words alone are compared with
shared words plus meaning. No database is used; the model runs locally.
"""

import sys
from pathlib import Path

# Direct runs put only scripts/ on the path; backend modules live one level up.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from features import ranking
from scripts.topic_match_cases import ADVISOR_TOPICS, CASES


def cosine(first, second):
    dot = sum(a * b for a, b in zip(first, second))
    lengths = (sum(a * a for a in first) ** 0.5) * (sum(b * b for b in second) ** 0.5)
    return dot / lengths if lengths else 0.0


def is_clear_winner(scores, right_index):
    """True when the right option scores strictly higher than every other option."""
    right = scores[right_index]
    return all(score < right for index, score in enumerate(scores) if index != right_index)


def evaluate_topic_matching(embedder, cases=CASES, advisor_topics=ADVISOR_TOPICS):
    """Return (shared-words hits, shared-words-plus-meaning hits, number of cases)."""
    topic_vectors = embedder.embed(advisor_topics)
    need_vectors = embedder.embed([need for need, _ in cases])
    words_hits = meaning_hits = 0
    for (need, right_index), need_vector in zip(cases, need_vectors):
        words = [ranking.topic_match(need, topics) for topics in advisor_topics]
        combined = [
            ranking.combined_topic_match(need, topics, cosine(need_vector, topic_vector))
            for topics, topic_vector in zip(advisor_topics, topic_vectors)
        ]
        words_hits += is_clear_winner(words, right_index)
        meaning_hits += is_clear_winner(combined, right_index)
    return words_hits, meaning_hits, len(cases)


def topic_eval_report(words_hits, meaning_hits, cases):
    def line(label, hits):
        return f"    {label:<28} {100 * hits / cases:.1f}% ({hits} of {cases})"

    return "\n".join([
        f"Topic matching eval: is the right advisor the clear top match? ({cases} cases, "
        f"{len(ADVISOR_TOPICS)} advisor topic lists)",
        line("Shared words only:", words_hits),
        line("Shared words and meaning:", meaning_hits),
        f"    Meaning stretch points: {ranking.MEANING_NO_MATCH} (no match) to "
        f"{ranking.MEANING_STRONG_MATCH} (strong match)",
    ])


def main():
    from core.embeddings import TopicEmbedder

    words_hits, meaning_hits, cases = evaluate_topic_matching(TopicEmbedder())
    print(topic_eval_report(words_hits, meaning_hits, cases))
    return 0


if __name__ == "__main__":
    sys.exit(main())
