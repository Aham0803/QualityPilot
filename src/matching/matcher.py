"""
MDM Entity Matcher & Clustering Engine.
Uses candidate blocking, RapidFuzz token matching, exact phone/email matching,
and computes Precision, Recall, and F1 score against ground truth entity clusters.
"""

import uuid
import difflib
from typing import Dict, Any, List, Tuple, Set
import pandas as pd
from collections import defaultdict

try:
    from rapidfuzz import fuzz, distance
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

from src.matching.standardizer import (
    clean_text,
    normalize_phone,
    normalize_email,
    normalize_postal,
    generate_blocking_key
)
from src.db.models import MatchPair, StewardQueue, get_session

def compute_similarity(str_a: str, str_b: str) -> float:
    """Return normalized similarity between 0.0 and 1.0."""
    if not str_a or not str_b:
        return 0.0
    if str_a == str_b:
        return 1.0

    if HAS_RAPIDFUZZ:
        # RapidFuzz token_sort_ratio handles reordered tokens like 'Rahul Sharma' vs 'Sharma Rahul'
        return fuzz.token_sort_ratio(str_a, str_b) / 100.0
    else:
        # High quality difflib fallback
        return difflib.SequenceMatcher(None, str_a, str_b).ratio()

class EntityMatcher:
    def __init__(
        self,
        weights: Dict[str, float] = None,
        auto_threshold: float = 0.90,
        review_threshold: float = 0.70,
        session = None
    ):
        self.weights = weights or {
            "name": 0.40,
            "address": 0.25,
            "email": 0.20,
            "phone": 0.15
        }
        self.auto_threshold = auto_threshold
        self.review_threshold = review_threshold
        self.session = session or get_session()

    def score_pair(self, rec_a: Dict[str, Any], rec_b: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
        """Calculate weighted composite similarity score between two records."""
        # 1. Name similarity
        name_a = clean_text(rec_a.get("full_name", ""))
        name_b = clean_text(rec_b.get("full_name", ""))
        name_score = compute_similarity(name_a, name_b)

        # 2. Address / City similarity
        addr_a = f"{clean_text(rec_a.get('address', ''))} {clean_text(rec_a.get('city', ''))}"
        addr_b = f"{clean_text(rec_b.get('address', ''))} {clean_text(rec_b.get('city', ''))}"
        addr_score = compute_similarity(addr_a, addr_b)

        # 3. Email exact match
        email_a = normalize_email(rec_a.get("email"))
        email_b = normalize_email(rec_b.get("email"))
        email_score = 1.0 if (email_a and email_b and email_a == email_b) else 0.0

        # 4. Phone exact match
        phone_a = normalize_phone(rec_a.get("phone"))
        phone_b = normalize_phone(rec_b.get("phone"))
        phone_score = 1.0 if (phone_a and phone_b and phone_a == phone_b) else 0.0

        # High-precision entity resolution boost
        # If email matches and names are very close (>= 0.82), strong evidence of same entity
        if email_score == 1.0 and name_score >= 0.82:
            composite = max(0.93, 0.45 * name_score + 0.35 * email_score + 0.20 * addr_score)
        # If phone matches and names are very close (>= 0.85)
        elif phone_score == 1.0 and name_score >= 0.85:
            composite = max(0.91, 0.50 * name_score + 0.30 * phone_score + 0.20 * addr_score)
        # If name is nearly identical (>= 0.92) and address is very close (>= 0.80)
        elif name_score >= 0.92 and addr_score >= 0.80:
            composite = max(0.90, 0.55 * name_score + 0.45 * addr_score)
        else:
            composite = (
                self.weights["name"] * name_score +
                self.weights["address"] * addr_score +
                self.weights["email"] * email_score +
                self.weights["phone"] * phone_score
            )

        details = {
            "name_score": round(name_score, 4),
            "address_score": round(addr_score, 4),
            "email_score": email_score,
            "phone_score": phone_score,
            "composite": round(composite, 4)
        }
        return composite, details

    def run_matching(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Execute blocking, candidate pair comparison, threshold classification,
        and database recording for auto-merge and steward review queues.
        """
        records = df.to_dict(orient="records")
        record_id_col = "source_record_id"

        # Step 1: Inverted index blocking on (name_prefix + postal_prefix) and (email) and (phone)
        blocks = defaultdict(list)
        email_blocks = defaultdict(list)
        phone_blocks = defaultdict(list)

        for idx, r in enumerate(records):
            b_key = generate_blocking_key(r.get("full_name", ""), r.get("postal_code", ""))
            blocks[b_key].append(idx)

            em = normalize_email(r.get("email"))
            if em:
                email_blocks[em].append(idx)

            ph = normalize_phone(r.get("phone"))
            if ph:
                phone_blocks[ph].append(idx)

        # Step 2: Form candidate comparison pairs
        candidate_pairs: Set[Tuple[int, int]] = set()

        for b_key, indices in blocks.items():
            if len(indices) > 1 and len(indices) < 500:  # Avoid runaway megablocks
                for i in range(len(indices)):
                    for j in range(i + 1, len(indices)):
                        candidate_pairs.add((indices[i], indices[j]))

        for em, indices in email_blocks.items():
            if len(indices) > 1:
                for i in range(len(indices)):
                    for j in range(i + 1, len(indices)):
                        candidate_pairs.add((indices[i], indices[j]))

        for ph, indices in phone_blocks.items():
            if len(indices) > 1:
                for i in range(len(indices)):
                    for j in range(i + 1, len(indices)):
                        candidate_pairs.add((indices[i], indices[j]))

        auto_merge_pairs = []
        steward_review_pairs = []
        distinct_count = 0

        # Step 3: Evaluate candidate pairs
        for idx_a, idx_b in candidate_pairs:
            rec_a = records[idx_a]
            rec_b = records[idx_b]
            id_a = str(rec_a.get(record_id_col, idx_a))
            id_b = str(rec_b.get(record_id_col, idx_b))

            score, details = self.score_pair(rec_a, rec_b)

            if score >= self.auto_threshold:
                decision = "auto_merge"
                auto_merge_pairs.append((id_a, id_b, score, details))
            elif score >= self.review_threshold:
                decision = "steward_review"
                steward_review_pairs.append((id_a, id_b, score, details))
            else:
                decision = "distinct"
                distinct_count += 1

            # Log match pair to DB (sample up to 1000 pairs to keep fast)
            if decision in ["auto_merge", "steward_review"]:
                pair_rec = MatchPair(
                    pair_id=f"PAIR-{uuid.uuid4().hex[:12].upper()}",
                    record_a=id_a,
                    record_b=id_b,
                    source_a=rec_a.get("source", "Unknown"),
                    source_b=rec_b.get("source", "Unknown"),
                    match_score=round(score, 4),
                    decision=decision,
                    details=str(details)
                )
                self.session.add(pair_rec)

                # If steward review, queue for human steward in steward_queue
                if decision == "steward_review":
                    task = StewardQueue(
                        task_id=f"TASK-{uuid.uuid4().hex[:10].upper()}",
                        task_type="duplicate_review",
                        record_id=f"{id_a} <-> {id_b}",
                        payload=f"Pair comparison between {rec_a.get('full_name')} and {rec_b.get('full_name')}",
                        ai_suggestion=f"Candidate duplicate with {round(score*100, 1)}% similarity. Merge recommended.",
                        ai_confidence=round(score, 2),
                        ai_reason=f"Name similarity: {details['name_score']}, Address similarity: {details['address_score']}",
                        status="PENDING"
                    )
                    self.session.add(task)

        self.session.commit()

        # Step 4: Build Connected Component Clusters for Auto-Merged Entities
        # Union-Find
        parent = {}
        def find(i):
            if parent.setdefault(i, i) != i:
                parent[i] = find(parent[i])
            return parent[i]

        def union(i, j):
            root_i = find(i)
            root_j = find(j)
            if root_i != root_j:
                parent[root_i] = root_j

        for id_a, id_b, _, _ in auto_merge_pairs:
            union(id_a, id_b)

        # Form clusters
        clusters = defaultdict(list)
        all_ids = set(str(r.get(record_id_col, i)) for i, r in enumerate(records))
        for rec_id in all_ids:
            root = find(rec_id)
            clusters[root].append(rec_id)

        cluster_list = list(clusters.values())

        return {
            "candidate_pairs_evaluated": len(candidate_pairs),
            "auto_merge_pairs_count": len(auto_merge_pairs),
            "steward_review_pairs_count": len(steward_review_pairs),
            "distinct_pairs_count": distinct_count,
            "clusters": cluster_list,
            "auto_pairs": auto_merge_pairs,
            "review_pairs": steward_review_pairs
        }

    def evaluate_against_ground_truth(
        self,
        auto_pairs: List[Tuple[str, str, float, Any]],
        df: pd.DataFrame,
        gt_col: str = "true_entity_id",
        id_col: str = "source_record_id"
    ) -> Dict[str, float]:
        """
        Evaluate duplicate-detection precision, recall, and F1 score against hidden ground truth.
        """
        if gt_col not in df.columns:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

        # Map each source_record_id to true_entity_id
        id_to_true = dict(zip(df[id_col].astype(str), df[gt_col].astype(str)))

        # Ground truth positive pairs
        true_clusters = defaultdict(list)
        for s_id, t_id in id_to_true.items():
            true_clusters[t_id].append(s_id)

        actual_positive_pairs = set()
        for t_id, ids in true_clusters.items():
            if len(ids) > 1:
                for i in range(len(ids)):
                    for j in range(i + 1, len(ids)):
                        actual_positive_pairs.add(tuple(sorted([ids[i], ids[j]])))

        # Predicted positive pairs from auto-merge
        predicted_pairs = set()
        for id_a, id_b, _, _ in auto_pairs:
            predicted_pairs.add(tuple(sorted([id_a, id_b])))

        true_positives = len(predicted_pairs.intersection(actual_positive_pairs))
        false_positives = len(predicted_pairs - actual_positive_pairs)
        false_negatives = len(actual_positive_pairs - predicted_pairs)

        precision = (true_positives / (true_positives + false_positives)) if (true_positives + false_positives) > 0 else 1.0
        recall = (true_positives / (true_positives + false_negatives)) if (true_positives + false_negatives) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        return {
            "precision": round(precision * 100.0, 2),
            "recall": round(recall * 100.0, 2),
            "f1": round(f1 * 100.0, 2),
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "total_actual_duplicates": len(actual_positive_pairs)
        }
