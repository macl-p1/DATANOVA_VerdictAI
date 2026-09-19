# Annotation guide

Annotate the shortest evidence span that explicitly supports a fact. Offsets are zero-based, end-exclusive, and page-local. Copy the entity `text` exactly from its page text.

Use `ARREST_DATE` only for language explicitly identifying arrest; a generic order date is not an arrest date. Use `RELEASE_DATE` only for an explicit release/bail date. Preserve dates exactly (`15.01.2024`, `15th January, 2024`); deterministic post-processing may normalize them later.

Use `LEGAL_SECTION` for the full statutory reference such as `Section 303 of BNS`, `u/s 303`, or `Sections 303 and 304`. Use `OFFENCE` for an expressly named offence, `CUSTODY_STATUS` for phrases such as `remanded to judicial custody`, and `MAX_SENTENCE` only for an explicit maximum-punishment statement.

Use `PENDING_CASES` for the whole statement, including negation: annotate `no other pending cases`, not merely `pending cases`. This preserves evidence for a later deterministic interpretation. Apply the same principle to `FIRST_TIME_OFFENDER`: annotate the stated phrase, not an inferred status.

`CASE_ID`, `COURT`, and `ACCUSED` should be explicit source spans. NER does not resolve relationships between them; do not invent associations between multiple accused and dates/sections. Overlapping entities are forbidden in the current canonical schema.

Mark data as `synthetic`, `public`, or `human_annotated`; never portray synthetic examples as real. A reviewer should set `review_status` after checking every span.
