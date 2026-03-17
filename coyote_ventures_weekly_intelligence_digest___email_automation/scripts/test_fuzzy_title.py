"""Quick test of fuzzy title matching — covers both the original Zomato case and Grow Therapy company-name deduplication."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.supabase_write_candidates import _title_is_fuzzy_duplicate, _extract_company_bigrams


def _section(header: str) -> None:
    print()
    print(f"=== {header} ===")
    print()


def main() -> None:
    # ------------------------------------------------------------------ #
    # 1. Original Zomato near-duplicate test (fuzz.ratio path)            #
    # ------------------------------------------------------------------ #
    _section('Zomato near-duplicates (fuzz.ratio >= 90 path)')
    zomato = "Zomato founder bets $54M on brain-monitoring wearable"
    near_dupes = [
        "Zomato founder bets $54M on brain-monitoring wearable",
        "Zomato founder bets $54M on brain-monitoring wearable device",
        "Zomato Founder Bets $54M On Brain-Monitoring Wearable",
        "Zomato founder bets 54M on brain-monitoring wearable",
    ]
    for t in near_dupes:
        from rapidfuzz import fuzz as _fuzz
        ratio = _fuzz.ratio(zomato.lower(), t.lower())
        dup = _title_is_fuzzy_duplicate(zomato, [t])
        display = t[:70] + "..." if len(t) > 70 else t
        print(f"  ratio={int(ratio):3d}  duplicate={dup}  | {display}")

    print()
    print("Unrelated titles (should NOT be duplicates):")
    for t in [
        "Healthcare AI startup raises $50M Series B",
        "Brain-monitoring tech gets FDA approval",
        "Zomato reports Q3 earnings",
    ]:
        from rapidfuzz import fuzz as _fuzz
        ratio = _fuzz.ratio(zomato.lower(), t.lower())
        dup = _title_is_fuzzy_duplicate(zomato, [t])
        print(f"  ratio={int(ratio):3d}  duplicate={dup}  | {t}")

    # ------------------------------------------------------------------ #
    # 2. Grow Therapy — same startup, different article angles             #
    # ------------------------------------------------------------------ #
    _section('Grow Therapy company-name deduplication')

    gt_titles = [
        "Grow Therapy raises $88M to expand mental health access",
        "Grow Therapy partners with Blue Cross for telehealth sessions",
        "How Grow Therapy is reshaping virtual behavioral care",
        "Grow Therapy secures $60M Series C funding round",
    ]
    # Simulate: first article already in DB, rest are new candidates
    existing_db = [gt_titles[0]]
    print(f"  Already in DB: '{existing_db[0]}'")
    print()
    for t in gt_titles[1:]:
        bigrams = _extract_company_bigrams(t)
        dup = _title_is_fuzzy_duplicate(t, existing_db)
        print(f"  bigrams={bigrams}  duplicate={dup}  | {t}")

    # ------------------------------------------------------------------ #
    # 3. False-positive guard — generic phrases must NOT trigger bigram    #
    # ------------------------------------------------------------------ #
    _section('False-positive guard: generic phrases (should NOT match "Grow Therapy")')
    generic_titles = [
        "Mental Health Startups Are Seeing Record Funding in 2026",
        "Digital Health Platform Raises Series B",
        "How Behavioral Health Companies Are Scaling in 2026",
    ]
    for t in generic_titles:
        bigrams = _extract_company_bigrams(t)
        dup = _title_is_fuzzy_duplicate(t, existing_db)
        print(f"  bigrams={bigrams}  duplicate={dup}  | {t}")


if __name__ == "__main__":
    main()
