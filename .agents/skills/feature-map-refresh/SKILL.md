---
name: feature-map-refresh
description: Review and refresh the repository's agent feature map after user-facing behavior or ownership changes.
---

# Feature map refresh

1. Run `python3 tools/feature_map.py --changed <ref>` for a known comparison ref, or `python3 tools/feature_map.py --all` to review every feature.
2. Read every listed feature file and every repository file matched by its `paths` frontmatter.
3. From the user's point of view, correct the title, vague-prompt aliases, discovered entry points, sub-features, how to reach it, how to drive it, and gotchas.
4. Keep descriptions truthful and compact. Keep each production file owned by exactly one feature. Do not edit the generated index directly.
5. Run `python3 tools/feature_map.py`, then `python3 tools/feature_map.py --check`.
6. Run `tools/verify.sh` before handing work back.

This repository has no release signing or distribution flow, so it intentionally has no semantic stamp or release guard. Structural freshness is enforced during normal verification and pre-commit.
