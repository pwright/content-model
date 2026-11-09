"""
Tiered heuristic matcher for upstream Skupper docs <-> downstream RHSI DITA docs.

Tier 1: Prefix-to-directory matching with title similarity (auto-accept above threshold)
Tier 2: Title similarity for unprefixed downstream topics (all to review)
Tier 3: Unmatched topics with near-miss candidates
"""

import re
import sys
import yaml
from collections import defaultdict
from pathlib import Path

STOP_WORDS = {
    "a", "an", "the", "and", "or", "of", "on", "in", "to", "for", "by",
    "using", "with", "from", "your", "you", "is", "are", "be", "that",
    "this", "it", "its", "at", "as", "do", "has", "have", "not", "can",
}

PREFIX_TO_DIR = {
    "kube-cli-": "kube-cli/",
    "kube-yaml-": "kube-yaml/",
    "system-cli-": "system-cli/",
    "system-yaml-": "system-yaml/",
    "console-": "console/",
    "overview-": "overview/",
    "troubleshooting-": "troubleshooting/",
}

DOWNSTREAM_ONLY_SECTIONS = {"whats-new", "pdfs"}


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def tokenize(text):
    text = re.sub(r"\{\{.*?\}\}", "skupper", text)
    words = re.findall(r"[a-z0-9]+", text.lower())
    return set(w for w in words if w not in STOP_WORDS and len(w) > 1)


def jaccard(set_a, set_b):
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def dam_filename(dam_path):
    return dam_path.rsplit("/", 1)[-1].replace(".dita", "")


def upstream_id(topic):
    if topic.get("anchor"):
        return f"{topic['path']}#{topic['anchor']}"
    return topic["path"]


def find_prefix(filename):
    for prefix, directory in PREFIX_TO_DIR.items():
        if filename.startswith(prefix):
            return prefix, directory
    return None, None


def is_jtbd(filename):
    return filename.startswith("jtbd-")


def best_matches(target_tokens, candidates, n=3):
    scored = []
    for cand in candidates:
        cand_tokens = tokenize(cand.get("title", ""))
        score = jaccard(target_tokens, cand_tokens)
        scored.append((score, cand))
    scored.sort(key=lambda x: -x[0])
    return scored[:n]


def main():
    base = Path(__file__).parent
    upstream_data = load_yaml(base / "upstream-inventory.yaml")
    downstream_data = load_yaml(base / "downstream-inventory.yaml")

    upstream_topics = upstream_data["upstream_topics"]
    downstream_topics = downstream_data["downstream_topics"]

    # Build upstream index by directory
    upstream_by_dir = defaultdict(list)
    for t in upstream_topics:
        directory = t["path"].split("/")[0] + "/" if "/" in t["path"] else ""
        upstream_by_dir[directory].append(t)

    # Track what's been matched
    matched_upstream = set()
    matched_downstream = set()

    # Results
    auto_accepted = []       # Tier 1 auto-accepted
    review_candidates = []   # Tier 2 + borderline Tier 1
    downstream_only = []     # Pre-classified
    tier1_scores = []        # For distribution analysis
    tier2_scores = []

    # --- Pre-classify downstream_only ---
    # Sections like whats-new and pdfs are always downstream_only.
    # jtbd-* topics are downstream_only UNLESS they have a strong title match
    # to an upstream topic (some jtbd-* assembly pages derive from upstream).
    all_upstream_tokens = {upstream_id(t): tokenize(t.get("title", ""))
                          for t in upstream_topics}
    for dt in downstream_topics:
        filename = dam_filename(dt["dam_path"])
        if dt.get("nav_section") in DOWNSTREAM_ONLY_SECTIONS:
            downstream_only.append(dt)
            matched_downstream.add(dt["guid"])
        elif is_jtbd(filename):
            dt_tokens = tokenize(dt.get("title", ""))
            has_strong_match = any(
                jaccard(dt_tokens, ut) >= 0.6
                for ut in all_upstream_tokens.values()
            )
            if not has_strong_match:
                downstream_only.append(dt)
                matched_downstream.add(dt["guid"])

    print(f"Pre-classified downstream_only: {len(downstream_only)}")

    # --- Tier 1: Prefix-to-directory matching ---
    for dt in downstream_topics:
        if dt["guid"] in matched_downstream:
            continue

        filename = dam_filename(dt["dam_path"])
        prefix, directory = find_prefix(filename)

        if prefix is None:
            continue

        # Find candidates in the matching upstream directory
        candidates = upstream_by_dir.get(directory, [])
        if not candidates:
            continue

        dt_tokens = tokenize(dt.get("title", ""))
        best = best_matches(dt_tokens, candidates)

        if best and best[0][0] > 0:
            score, match = best[0]
            tier1_scores.append(score)

    # Determine empirical threshold from Tier 1 score distribution
    if tier1_scores:
        tier1_scores_sorted = sorted(tier1_scores)
        # Look for a natural gap; use 0.15 as a safe floor
        threshold = 0.15
        print(f"\nTier 1 score distribution ({len(tier1_scores)} matches):")
        buckets = defaultdict(int)
        for s in tier1_scores_sorted:
            bucket = round(s, 1)
            buckets[bucket] += 1
        for bucket in sorted(buckets):
            bar = "#" * buckets[bucket]
            print(f"  {bucket:.1f}: {bar} ({buckets[bucket]})")
        print(f"  Min: {min(tier1_scores):.3f}, Max: {max(tier1_scores):.3f}, "
              f"Median: {tier1_scores_sorted[len(tier1_scores_sorted)//2]:.3f}")
        print(f"  Auto-accept threshold: {threshold}")
    else:
        threshold = 0.15

    # Now do the actual Tier 1 matching with the threshold
    for dt in downstream_topics:
        if dt["guid"] in matched_downstream:
            continue

        filename = dam_filename(dt["dam_path"])
        prefix, directory = find_prefix(filename)

        if prefix is None:
            continue

        candidates = upstream_by_dir.get(directory, [])
        if not candidates:
            continue

        dt_tokens = tokenize(dt.get("title", ""))
        best = best_matches(dt_tokens, candidates)

        if best and best[0][0] >= threshold:
            score, match = best[0]
            uid = upstream_id(match)

            if score >= threshold:
                auto_accepted.append({
                    "upstream": uid,
                    "downstream": dt["guid"],
                    "derivation_type": "direct_port",
                    "tier": 1,
                    "score": round(score, 3),
                    "upstream_title": match.get("title", ""),
                    "downstream_title": dt.get("title", ""),
                })
                matched_upstream.add(uid)
                matched_downstream.add(dt["guid"])
            # Also add runners-up as review candidates if they scored well
            for s, m in best[1:]:
                if s >= threshold:
                    review_candidates.append({
                        "upstream": upstream_id(m),
                        "downstream": dt["guid"],
                        "score": round(s, 3),
                        "tier": 1,
                        "note": "runner-up match",
                        "upstream_title": m.get("title", ""),
                        "downstream_title": dt.get("title", ""),
                    })
        elif best and best[0][0] > 0:
            # Below threshold but non-zero: review candidate
            score, match = best[0]
            review_candidates.append({
                "upstream": upstream_id(match),
                "downstream": dt["guid"],
                "score": round(score, 3),
                "tier": 1,
                "note": "below threshold",
                "upstream_title": match.get("title", ""),
                "downstream_title": dt.get("title", ""),
            })
            matched_downstream.add(dt["guid"])

    print(f"\nTier 1 auto-accepted: {len(auto_accepted)}")

    # --- Tier 2: Title similarity for unprefixed ---
    remaining_upstream = [t for t in upstream_topics
                          if upstream_id(t) not in matched_upstream]
    remaining_downstream = [t for t in downstream_topics
                            if t["guid"] not in matched_downstream]

    print(f"\nTier 2 candidates: {len(remaining_downstream)} downstream, "
          f"{len(remaining_upstream)} upstream remaining")

    tier2_auto_threshold = 0.6
    for dt in remaining_downstream:
        dt_tokens = tokenize(dt.get("title", ""))
        best = best_matches(dt_tokens, remaining_upstream)

        if best and best[0][0] > 0:
            top_score, top_match = best[0]
            if top_score >= tier2_auto_threshold:
                uid = upstream_id(top_match)
                auto_accepted.append({
                    "upstream": uid,
                    "downstream": dt["guid"],
                    "derivation_type": "direct_port",
                    "tier": 2,
                    "score": round(top_score, 3),
                    "upstream_title": top_match.get("title", ""),
                    "downstream_title": dt.get("title", ""),
                })
                matched_upstream.add(uid)
                tier2_scores.append(top_score)
            for score, match in best:
                if score > 0 and not (score >= tier2_auto_threshold and match is top_match):
                    tier2_scores.append(score)
                    review_candidates.append({
                        "upstream": upstream_id(match),
                        "downstream": dt["guid"],
                        "score": round(score, 3),
                        "tier": 2,
                        "note": "title similarity",
                        "upstream_title": match.get("title", ""),
                        "downstream_title": dt.get("title", ""),
                    })
        matched_downstream.add(dt["guid"])

    if tier2_scores:
        print(f"\nTier 2 score distribution ({len(tier2_scores)} candidate pairs):")
        buckets = defaultdict(int)
        for s in tier2_scores:
            bucket = round(s, 1)
            buckets[bucket] += 1
        for bucket in sorted(buckets):
            bar = "#" * buckets[bucket]
            print(f"  {bucket:.1f}: {bar} ({buckets[bucket]})")

    # --- Tier 3: Unmatched with near-misses ---
    final_unmatched_upstream = [t for t in upstream_topics
                                 if upstream_id(t) not in matched_upstream]
    final_unmatched_downstream = [t for t in downstream_topics
                                   if t["guid"] not in matched_downstream]

    tier3_upstream = []
    for ut in final_unmatched_upstream:
        ut_tokens = tokenize(ut.get("title", ""))
        near = best_matches(ut_tokens, downstream_topics, n=3)
        tier3_upstream.append({
            "upstream": upstream_id(ut),
            "upstream_title": ut.get("title", ""),
            "source_category": ut.get("source_category", ""),
            "near_misses": [{
                "downstream": m["guid"],
                "downstream_title": m.get("title", ""),
                "score": round(s, 3),
            } for s, m in near if s > 0]
        })

    tier3_downstream = []
    for dt in final_unmatched_downstream:
        dt_tokens = tokenize(dt.get("title", ""))
        near = best_matches(dt_tokens, upstream_topics, n=3)
        tier3_downstream.append({
            "downstream": dt["guid"],
            "downstream_title": dt.get("title", ""),
            "nav_section": dt.get("nav_section", ""),
            "near_misses": [{
                "upstream": upstream_id(m),
                "upstream_title": m.get("title", ""),
                "score": round(s, 3),
            } for s, m in near if s > 0]
        })

    print(f"\nTier 3 unmatched upstream: {len(final_unmatched_upstream)}")
    print(f"Tier 3 unmatched downstream: {len(final_unmatched_downstream)}")

    # --- Build output: mappings.yaml ---
    all_upstream = []
    for t in upstream_topics:
        entry = {
            "id": upstream_id(t),
            "path": t["path"],
            "title": t.get("title", ""),
            "source_category": t.get("source_category", "guide"),
        }
        if t.get("anchor"):
            entry["anchor"] = t["anchor"]
        if t.get("content_type"):
            entry["content_type"] = t["content_type"]
        if t.get("status"):
            entry["status"] = t["status"]
        all_upstream.append(entry)

    all_downstream = []
    for t in downstream_topics:
        entry = {
            "id": t["guid"],
            "dam_path": t["dam_path"],
            "title": t.get("title", ""),
        }
        if t.get("dita_type"):
            entry["dita_type"] = t["dita_type"]
        if t.get("nav_section"):
            entry["nav_section"] = t["nav_section"]
        all_downstream.append(entry)

    mappings_list = []
    for m in auto_accepted:
        mappings_list.append({
            "upstream": m["upstream"],
            "downstream": m["downstream"],
            "derivation_type": m["derivation_type"],
        })

    output = {
        "upstream_topics": all_upstream,
        "downstream_topics": all_downstream,
        "mappings": mappings_list,
    }

    with open(base / "mappings.yaml", "w") as f:
        yaml.dump(output, f, default_flow_style=False, sort_keys=False,
                  allow_unicode=True, width=120)

    # --- Build output: review-candidates.yaml ---
    review_output = {
        "auto_accept_threshold": threshold,
        "tier1_auto_accepted_count": len(auto_accepted),
        "tier2_candidates": [c for c in review_candidates if c["tier"] == 2],
        "tier1_review": [c for c in review_candidates if c["tier"] == 1],
        "tier3_unmatched_upstream": tier3_upstream,
        "tier3_unmatched_downstream": tier3_downstream,
        "downstream_only": [{
            "downstream": d["guid"],
            "title": d.get("title", ""),
            "nav_section": d.get("nav_section", ""),
            "reason": "jtbd prefix" if is_jtbd(dam_filename(d["dam_path"])) else f"{d.get('nav_section', '')} section",
        } for d in downstream_only],
    }

    with open(base / "review-candidates.yaml", "w") as f:
        yaml.dump(review_output, f, default_flow_style=False, sort_keys=False,
                  allow_unicode=True, width=120)

    # Summary
    print(f"\n=== Summary ===")
    print(f"Total upstream topics:   {len(upstream_topics)}")
    print(f"Total downstream topics: {len(downstream_topics)}")
    print(f"Pre-classified downstream_only: {len(downstream_only)}")
    print(f"Tier 1 auto-accepted mappings:  {len(auto_accepted)}")
    print(f"Review candidates (Tier 1+2):   {len(review_candidates)}")
    print(f"Unmatched upstream (Tier 3):     {len(final_unmatched_upstream)}")
    print(f"Unmatched downstream (Tier 3):   {len(final_unmatched_downstream)}")
    print(f"\nWrote: content-model/mappings.yaml")
    print(f"Wrote: content-model/review-candidates.yaml")


if __name__ == "__main__":
    main()
