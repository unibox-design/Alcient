
import re
from collections import Counter
from typing import List

# Basic stopword list to keep keyword extraction lean for demo purposes.
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "your", "have", "are",
    "will", "into", "about", "into", "more", "than", "their", "they", "them",
    "when", "where", "what", "which", "while", "there", "these", "those",
    "because", "would", "could", "should", "being", "been", "also", "over",
    "after", "before", "around", "through", "every", "other", "some", "much",
    "many", "just", "into", "onto", "onto", "each", "such", "like", "make",
    "making", "take", "taking", "used", "using", "use", "uses", "very", "it's",
    "its", "it's", "our", "ours", "you", "your", "yours", "his", "her", "hers",
    "him", "she", "himself", "herself", "we", "us", "was", "were", "been", "had",
    "has", "have", "can", "can't", "cannot", "is", "isn't", "am", "i'm", "me",
    "my", "mine", "it's", "it's", "on", "off", "out", "in", "of", "to", "at",
    "by", "an", "a", "as", "be", "do", "does", "did", "or", "if", "so", "it's",
}


def extract_keywords(text: str, limit: int = 5) -> List[str]:
    """
    Heuristically pick a handful of keywords from free-form text.

    A lightweight alternative to calling the LLM – good enough for local demos.
    """
    if not text:
        return []

    words = re.findall(r"[A-Za-z0-9']+", text.lower())
    filtered = [w for w in words if len(w) > 2 and w not in _STOPWORDS and not w.isdigit()]
    if not filtered:
        return []

    counts = Counter(filtered)
    ranked = [word for word, _count in counts.most_common(limit * 2)]

    # Preserve order while de-duplicating and keep top `limit`.
    seen = set()
    keywords = []
    for word in ranked:
        if word in seen:
            continue
        seen.add(word)
        keywords.append(word)
        if len(keywords) >= limit:
            break

    return keywords
