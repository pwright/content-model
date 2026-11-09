# Content Provenance Model

Tracks provenance relationships between upstream Skupper community docs (Markdown) and downstream Red Hat Service Interconnect 2.2 DITA docs (AEM).

Built with [LinkML](https://linkml.io/) for schema-first validation and JSON Schema generation.

## Files

| File | Purpose |
|------|---------|
| `schema.yaml` | LinkML schema defining UpstreamTopic, DownstreamTopic, and ContentMapping classes |
| `mappings.yaml` | Instance data: all topics from both doc sets plus provenance mappings (hand-corrected beyond matcher output — re-running `match.py` will overwrite corrections) |
| `upstream-inventory.yaml` | Raw inventory of upstream content units extracted from `skupper-docs/input/` |
| `downstream-inventory.yaml` | Raw inventory of downstream DITA topics extracted from the AEM map export |
| `review-candidates.yaml` | Tier 2/3 match candidates and near-misses (review complete — archival) |
| `match.py` | Heuristic matcher that produces `mappings.yaml` from the inventories |
| `fix_inventory.py` | Utility that re-extracts section-level upstream units from multi-section files |

## How matching works

The matcher (`match.py`) runs in tiers, from highest confidence to lowest:

### Pre-classification

Downstream topics in the `whats-new` or `pdfs` nav sections are marked `downstream_only` unconditionally. Topics with `jtbd-*` filenames are marked `downstream_only` unless they have a strong title match (Jaccard >= 0.6) to an upstream topic.

### Tier 1: Prefix-to-directory

Downstream DAM filenames encode the upstream interface method as a prefix. The matcher maps these prefixes to upstream directories:

| Downstream prefix | Upstream directory |
|---|---|
| `kube-cli-*` | `kube-cli/` |
| `kube-yaml-*` | `kube-yaml/` |
| `system-cli-*` | `system-cli/` |
| `system-yaml-*` | `system-yaml/` |
| `console-*` | `console/` |
| `overview-*` | `overview/` |
| `troubleshooting-*` | `troubleshooting/` |

Within the matched directory, the downstream topic's title is fuzzy-matched against upstream topic titles using Jaccard similarity on lowercased word tokens (with stop words removed). Matches scoring above the auto-accept threshold (currently 0.15) are accepted automatically with `derivation_type: direct_port`.

### Tier 2: Title similarity

Downstream topics with no matching prefix are fuzzy-matched by title against all remaining unmatched upstream topics. Matches scoring >= 0.6 are auto-accepted. Lower-scoring matches are added to `review-candidates.yaml` for human review.

### Tier 3: Near-miss candidates

Remaining unmatched upstream and downstream topics are listed with their 3 closest near-miss matches from the opposite set, to help the human reviewer spot missed relationships.

## Adjusting the matcher

### Adding prefix mappings

If new upstream directories appear or downstream naming conventions change, add entries to `PREFIX_TO_DIR` in `match.py`:

```python
PREFIX_TO_DIR = {
    "kube-cli-": "kube-cli/",
    # add new prefixes here
}
```

### Changing the auto-accept threshold

**Tier 1 threshold** (`threshold` variable, currently 0.15): controls how strong a title match must be within a prefix-matched directory. Low because the prefix already confirms the domain. Raise this if you see false positives in Tier 1.

**Tier 2 threshold** (`tier2_auto_threshold` variable, currently 0.6): controls when title-only matches are auto-accepted without prefix confirmation. Higher because there's no prefix signal. Lower this to auto-accept more fuzzy matches; raise it to send more to review.

### Changing the jtbd-* reclassification threshold

In the pre-classification section, `jtbd-*` topics with a title match >= 0.6 to any upstream topic are kept in the matching pipeline instead of being marked `downstream_only`. Adjust this threshold if too many or too few jtbd-* topics are being reclassified.

### Re-running after changes

```bash
# From the repo root:
python3 -I content-model/match.py
```

This overwrites `mappings.yaml` and `review-candidates.yaml`. The inventories are not regenerated; to update those, re-run `fix_inventory.py` or re-extract from the source files.

## Derivation types

| Type | Meaning |
|------|---------|
| `direct_port` | Content moved across with minimal changes (branding, templates) |
| `rewritten` | Same topic, substantially rewritten for downstream audience |
| `restructured` | Upstream content broken apart or merged with other material downstream |
| `downstream_only` | No upstream source (release notes, supported configs, subscription topics) |
| `upstream_only` | Exists upstream with no downstream counterpart |
| `shared_source` | Both derive from a common source outside either doc set |

## Upstream source categories

- **guide**: How-to, conceptual, and procedural content from the main skupper-docs directories
- **reference**: API reference, CLI reference, and concept definitions from the `refdog/` section (currently marked `needs_work`)

## Validation

With LinkML installed, validate the mappings against the schema:

```bash
linkml-validate -s content-model/schema.yaml content-model/mappings.yaml
```

Generate JSON Schema for editor support:

```bash
gen-json-schema content-model/schema.yaml > content-model/schema.json
```
