# Block33 offline FRF correction protocol

Scope: reproduce reported defects before edits, correct mission-neutral library,
ordinary synthetic/transport tests, clean tracked-tree verification and cached
four-case regression into a new directory. No actual HTTP, downloads, SAR,
inversion, commit/push or modifications of Block32 artifacts/config/manifests.

Initial Git HEAD: 8d727db. Pre-existing untracked Blocks23–31 and their sources
are user-owned and remain unchanged. Use project thesis interpreter only.
Snapshot all available Block32 non-cache artifacts and cache bytes before work.
Tests simulate HTTP; their counters are not actual HTTP consumption.

Temporal policy: per-family half-width is max(event_context_seconds, configured
family tolerance). Discover every intersecting calendar month; merge only
overlapping event windows. Retain file/index provenance, different-grid tensors
and duplicate conflicts. Nearest is only within verified search coverage.

No new physical thresholds, direction corrections or scene classification.
