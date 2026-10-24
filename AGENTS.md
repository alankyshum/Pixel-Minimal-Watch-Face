# Repository rules

Run `tools/verify.sh` before handing work back. Fix failures rather than weakening the checks.

For vague or feature-level prompts, read `.agents/feature-map/README.md` first and then the matching feature file. Update the owning feature file whenever a code or resource change alters user-facing behavior or ownership. Do not hand-edit the generated index; run `python3 tools/feature_map.py` and stage its result.

The feature map requires every production file under the Android modules' `src/main` trees to have exactly one owner and every discovered watch-face, activity, receiver, and complication-provider entry point to have exactly one claim.

Use the repo-local `.agents/skills/feature-map-refresh/SKILL.md` procedure for a semantic feature-map review. There is no semantic stamp or release guard because this repository has no supported release signing or artifact-distribution flow.
