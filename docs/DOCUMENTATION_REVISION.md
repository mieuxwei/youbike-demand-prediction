# Public documentation revision — 2026-09-27

This revision changes public documentation and adds two real interface screenshots. Research, models, evaluation results, collector behavior, website source and deployed versions remain frozen. It is not a new experiment or release.

## Relationship to the accepted versions

| Record | Meaning | Treatment |
|---|---|---|
| Research preservation commit `159f059d0e9ff4afcdbf9ad206d1b426aa1339aa` | Original local Phase 3–4 acceptance alongside Track A and Stage 17/19 | Original reports, protocol and manifest retained |
| Live implementation `f3e27e055195818c3c4ddc4e53d92bd18c1c1cdf` | Public 12-station serving and interface | Runtime source unchanged |
| Delivery freeze `176f8c594f24bf5f35037bf78974069c9863a576` | Accepted source/document boundary; 283 file hashes | Original manifest retained unchanged |
| This documentation revision | Four primary entries, concise results, real screenshots and technical evidence navigation | Exact file changes recorded separately in [the amendment](publication/documentation-amendment.json) |

The [original research acceptance](https://github.com/mieuxwei/youbike-demand-prediction/blob/159f059d0e9ff4afcdbf9ad206d1b426aa1339aa/docs/RESEARCH_FREEZE.md) and [live delivery acceptance](LIVE_DEMO_DELIVERY.md) retain their dated context, deployment identities and unverified checks. They are evidence, not current work instructions.

## Content retained and navigation changes

The internal `HANDOFF.md` and `PROJECT_PLAN.md` are removed from the current source tree after complete external backup. Original phase mapping, track boundaries, model decisions, architecture, failure gates, limitations and reproduction entry points are retained in the [Chinese overview](PROJECT_OVERVIEW_STATUS_AND_TECHNOLOGY.md), [evidence index](README.md), existing reports and [reproduction guide](REPRODUCIBILITY.md). No raw research data, results or model files were removed.

The model card changes only its obsolete plan-reference paragraph. The reproducibility guide distinguishes the historical holdout section from live serving and uses the current documentation-integrity check. Existing research commands and parameters remain documented for isolated reproduction.

No Git history is rewritten. Previous commits still contain the internal files; removing them from a working tree is not removal from a published branch until that change is committed and pushed.

## Integrity checks

```bash
python3 scripts/verify_publication.py
python3 -m unittest tests.test_publication_integrity -v
git diff --check
```

The additive amendment records before/after SHA-256 values and explicit removals. Checks require a Git checkout containing the two original commits above (not a source ZIP or a shallow checkout without that history). The verifier:

- Checks both original manifests and acceptance records against the delivery commit.
- Checks every one of the 283 original delivery files, accepting only the exact recorded documentation changes or removals.
- Checks new documentation, screenshots and the verification code against their hashes.
- Resolves local Markdown links and heading anchors in current documents.
- Treats the single old plan link inside the unchanged original research freeze as a historical link, verifying the target at its preservation commit instead of silently skipping it.

It does not train, infer, export cloud data, change settings or refresh an original manifest. The amendment excludes its own hash to avoid a circular reference; Git review/commit identity provides its version boundary. Hash consistency is not a digital signature.

## Original version checks

The original whole-delivery verifiers deliberately reject later documentation edits. Their behavior is preserved, not weakened with a blanket exclusion. To verify the exact original versions, use a separate checkout:

```bash
git clone https://github.com/mieuxwei/youbike-demand-prediction.git /tmp/youbike-v7-verification
git -C /tmp/youbike-v7-verification checkout --detach 176f8c594f24bf5f35037bf78974069c9863a576
cd /tmp/youbike-v7-verification
python3 src/freeze_live_demo.py verify
# The earlier local-only research record:
git checkout --detach 159f059d0e9ff4afcdbf9ad206d1b426aa1339aa
python3 src/freeze_offline_research.py verify
```

Use an unused destination path; these are reproduction instructions, not commands needed to view the demo. Original `freeze_offline_research.py check` additionally needs its recorded local data/cache and the original checkout; it is not a lightweight documentation check.

## Historical evidence kept intact

`docs/RESEARCH_FREEZE.md`, `docs/LIVE_DEMO_DELIVERY.md`, the serving/research protocols, dated Stage reports and original manifests are retained byte-for-byte even where they contain historical execution context. Altering them would change acceptance or prospective evidence. The original freeze's relative plan link resolves in the linked historical commit; current navigation no longer relies on it. The old verifier's plan/handoff names also remain as historical manifest identifiers, not input-file dependencies.

The current demo uses the same Sites version 3 and Worker deployment recorded in the delivery report. Documentation screenshots are dated illustrations, not a redeployment or additional forecast-quality evaluation. Physical-phone/Safari-private testing and long-term availability are not newly claimed by this revision.
