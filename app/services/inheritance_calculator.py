"""
Inheritance Calculator Engine
Supports:
- Islamic Law (Hanafi school - predominant in Pakistan)
- Christian Law (Succession Act 1925)
- Hindu Law (Hindu Succession Act as applicable in Pakistan)
- Sikh Law (customary / Succession Act 1925)
- Shia Islamic Law (Ithna Ashari - Jafari school)

References:
- Muslim Family Laws Ordinance 1961
- West Pakistan Muslim Personal Law (Shariat) Application Act 1962
- Succession Act 1925 (for non-Muslims)
- The Quran (Surah An-Nisa, 4:11-12, 4:176)
"""

from fractions import Fraction
from typing import Optional
from enum import Enum


class Religion(str, Enum):
    SUNNI_HANAFI = "sunni_hanafi"
    SHIA = "shia"
    CHRISTIAN = "christian"
    HINDU = "hindu"
    SIKH = "sikh"


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"


class Relationship(str, Enum):
    # Spouse
    HUSBAND = "husband"
    WIFE = "wife"
    # Children
    SON = "son"
    DAUGHTER = "daughter"
    # Grandchildren (through son)
    SONS_SON = "sons_son"
    SONS_DAUGHTER = "sons_daughter"
    # Parents
    FATHER = "father"
    MOTHER = "mother"
    # Grandparents
    PATERNAL_GRANDFATHER = "paternal_grandfather"
    PATERNAL_GRANDMOTHER = "paternal_grandmother"
    MATERNAL_GRANDMOTHER = "maternal_grandmother"
    # Siblings
    FULL_BROTHER = "full_brother"
    FULL_SISTER = "full_sister"
    PATERNAL_HALF_BROTHER = "paternal_half_brother"
    PATERNAL_HALF_SISTER = "paternal_half_sister"
    MATERNAL_HALF_BROTHER = "maternal_half_brother"
    MATERNAL_HALF_SISTER = "maternal_half_sister"
    # Nephews (brother's sons) - Asaba
    FULL_NEPHEW = "full_nephew"
    PATERNAL_NEPHEW = "paternal_nephew"
    FULL_NEPHEWS_SON = "full_nephews_son"
    PATERNAL_NEPHEWS_SON = "paternal_nephews_son"
    # Paternal Uncles - Asaba
    FULL_PATERNAL_UNCLE = "full_paternal_uncle"
    PATERNAL_PATERNAL_UNCLE = "paternal_paternal_uncle"
    # Cousins (uncle's sons) - Asaba
    FULL_COUSIN = "full_cousin"
    PATERNAL_COUSIN = "paternal_cousin"
    FULL_COUSINS_SON = "full_cousins_son"
    PATERNAL_COUSINS_SON = "paternal_cousins_son"
    FULL_COUSINS_GRANDSON = "full_cousins_grandson"
    PATERNAL_COUSINS_GRANDSON = "paternal_cousins_grandson"
    # Extended (for Christian/Hindu)
    UNCLE = "uncle"
    AUNT = "aunt"
    NEPHEW = "nephew"
    NIECE = "niece"
    COUSIN = "cousin"


class Heir:
    def __init__(self, name: str, relationship: str, gender: str, count: int = 1):
        self.name = name
        self.relationship = relationship
        self.gender = gender
        self.count = count
        self.share: Optional[Fraction] = None
        self.share_amount: float = 0.0
        self.blocked: bool = False
        self.blocked_by: str = ""
        self.basis: str = ""  # Legal basis / Quranic reference

    def to_dict(self):
        return {
            "name": self.name,
            "relationship": self.relationship,
            "gender": self.gender,
            "count": self.count,
            "share_fraction": str(self.share) if self.share else "0",
            "share_percentage": round(float(self.share) * 100, 4) if self.share else 0,
            "share_amount": round(self.share_amount, 2),
            "blocked": self.blocked,
            "blocked_by": self.blocked_by,
            "basis": self.basis,
        }


def _has(heirs: list[Heir], rel: str) -> bool:
    return any(h.relationship == rel and not h.blocked for h in heirs)


def _count(heirs: list[Heir], rel: str) -> int:
    return sum(h.count for h in heirs if h.relationship == rel and not h.blocked)


def _get(heirs: list[Heir], rel: str) -> list[Heir]:
    return [h for h in heirs if h.relationship == rel and not h.blocked]


def _has_any(heirs: list[Heir], rels: list[str]) -> bool:
    return any(_has(heirs, r) for r in rels)


def _has_children(heirs: list[Heir]) -> bool:
    return _has_any(heirs, [Relationship.SON, Relationship.DAUGHTER])


def _has_male_descendants(heirs: list[Heir]) -> bool:
    return _has_any(heirs, [Relationship.SON, Relationship.SONS_SON])


def _has_descendants(heirs: list[Heir]) -> bool:
    return _has_any(heirs, [
        Relationship.SON, Relationship.DAUGHTER,
        Relationship.SONS_SON, Relationship.SONS_DAUGHTER
    ])


def _siblings_count(heirs: list[Heir]) -> int:
    sibling_rels = [
        Relationship.FULL_BROTHER, Relationship.FULL_SISTER,
        Relationship.PATERNAL_HALF_BROTHER, Relationship.PATERNAL_HALF_SISTER,
        Relationship.MATERNAL_HALF_BROTHER, Relationship.MATERNAL_HALF_SISTER,
    ]
    return sum(_count(heirs, r) for r in sibling_rels)


# ─── ISLAMIC (SUNNI HANAFI) INHERITANCE ──────────────────────────────────

def calculate_islamic_hanafi(heirs: list[Heir], total_estate: float, debts: float = 0, bequests: float = 0) -> dict:
    """
    Calculate inheritance according to Sunni Hanafi fiqh (predominant in Pakistan).
    Based on Quran 4:11-12, 4:176 and Hanafi jurisprudence.
    """
    # Step 1: Deduct debts, then bequests (max 1/3 of remainder)
    net_estate = total_estate - debts
    max_bequest = net_estate / 3
    actual_bequest = min(bequests, max_bequest)
    distributable = net_estate - actual_bequest

    # Step 2: Apply blocking rules (Hajb)
    _apply_hanafi_blocking(heirs)

    # Step 3: Assign fixed shares (Fard)
    fixed_shares: dict[str, Fraction] = {}
    residuary_heirs: list[Heir] = []

    for heir in heirs:
        if heir.blocked:
            continue

        rel = heir.relationship

        # ── HUSBAND ──
        if rel == Relationship.HUSBAND:
            if _has_descendants(heirs):
                heir.share = Fraction(1, 4)
                heir.basis = "Quran 4:12 - Husband gets 1/4 when deceased has children"
            else:
                heir.share = Fraction(1, 2)
                heir.basis = "Quran 4:12 - Husband gets 1/2 when deceased has no children"
            fixed_shares[heir.name] = heir.share

        # ── WIFE ──
        elif rel == Relationship.WIFE:
            if _has_descendants(heirs):
                heir.share = Fraction(1, 8)
                heir.basis = "Quran 4:12 - Wife gets 1/8 when deceased has children"
            else:
                heir.share = Fraction(1, 4)
                heir.basis = "Quran 4:12 - Wife gets 1/4 when deceased has no children"
            # If multiple wives, they share the portion
            wife_count = _count(heirs, Relationship.WIFE)
            if wife_count > 1:
                heir.share = heir.share / wife_count
                heir.basis += f" (shared equally among {wife_count} wives)"
            fixed_shares[heir.name] = heir.share

        # ── FATHER ──
        elif rel == Relationship.FATHER:
            if _has_male_descendants(heirs):
                heir.share = Fraction(1, 6)
                heir.basis = "Quran 4:11 - Father gets 1/6 when deceased has male descendants"
                fixed_shares[heir.name] = heir.share
            elif _has_descendants(heirs):
                # Father gets 1/6 as fixed share + residuary
                heir.share = Fraction(1, 6)
                heir.basis = "Quran 4:11 - Father gets 1/6 fixed + residuary when only daughters exist"
                fixed_shares[heir.name] = heir.share
                residuary_heirs.append(heir)
            else:
                heir.basis = "Quran 4:11 - Father is residuary heir when no descendants"
                residuary_heirs.append(heir)

        # ── MOTHER ──
        elif rel == Relationship.MOTHER:
            if _has_descendants(heirs) or _siblings_count(heirs) >= 2:
                heir.share = Fraction(1, 6)
                if _has_descendants(heirs):
                    heir.basis = "Quran 4:11 - Mother gets 1/6 when deceased has children"
                else:
                    heir.basis = "Quran 4:11 - Mother gets 1/6 when deceased has 2+ siblings"
            else:
                # Umariyyatan case: spouse + both parents, no children
                if (_has(heirs, Relationship.HUSBAND) or _has(heirs, Relationship.WIFE)) and _has(heirs, Relationship.FATHER):
                    # Mother gets 1/3 of remainder after spouse's share
                    spouse_share = Fraction(0)
                    if _has(heirs, Relationship.HUSBAND):
                        spouse_share = Fraction(1, 2)
                    elif _has(heirs, Relationship.WIFE):
                        spouse_share = Fraction(1, 4)
                    remainder_fraction = Fraction(1) - spouse_share
                    heir.share = remainder_fraction * Fraction(1, 3)
                    heir.basis = "Umariyyatan case - Mother gets 1/3 of remainder after spouse's share"
                else:
                    heir.share = Fraction(1, 3)
                    heir.basis = "Quran 4:11 - Mother gets 1/3 when no children and fewer than 2 siblings"
            fixed_shares[heir.name] = heir.share

        # ── DAUGHTER(S) ──
        elif rel == Relationship.DAUGHTER:
            if _has(heirs, Relationship.SON):
                # Residuary with son (2:1 ratio)
                heir.basis = "Quran 4:11 - Daughter as residuary with son (son gets double)"
                residuary_heirs.append(heir)
            else:
                daughter_count = _count(heirs, Relationship.DAUGHTER)
                if daughter_count == 1:
                    heir.share = Fraction(1, 2)
                    heir.basis = "Quran 4:11 - Single daughter gets 1/2"
                else:
                    heir.share = Fraction(2, 3) / daughter_count
                    heir.basis = f"Quran 4:11 - Daughters share 2/3 equally ({daughter_count} daughters)"
                fixed_shares[heir.name] = heir.share

        # ── SON(S) ──
        elif rel == Relationship.SON:
            heir.basis = "Quran 4:11 - Son is residuary heir (Asaba)"
            residuary_heirs.append(heir)

        # ── SON'S SON (Grandson through son) ──
        elif rel == Relationship.SONS_SON:
            heir.basis = "Son's son is residuary heir in absence of son"
            residuary_heirs.append(heir)

        # ── SON'S DAUGHTER (Granddaughter through son) ──
        elif rel == Relationship.SONS_DAUGHTER:
            if not _has(heirs, Relationship.SON):
                if _has(heirs, Relationship.SONS_SON):
                    heir.basis = "Son's daughter as residuary with son's son (2:1)"
                    residuary_heirs.append(heir)
                else:
                    daughter_count = _count(heirs, Relationship.DAUGHTER)
                    sd_count = _count(heirs, Relationship.SONS_DAUGHTER)
                    if daughter_count == 0:
                        if sd_count == 1:
                            heir.share = Fraction(1, 2)
                            heir.basis = "Son's daughter gets 1/2 (like daughter in absence of children)"
                        else:
                            heir.share = Fraction(2, 3) / sd_count
                            heir.basis = f"Son's daughters share 2/3 equally ({sd_count})"
                    elif daughter_count == 1:
                        heir.share = Fraction(1, 6) / sd_count
                        heir.basis = "Son's daughter gets 1/6 to complete 2/3 (with one daughter)"
                    else:
                        heir.blocked = True
                        heir.blocked_by = "2+ daughters"
                        heir.basis = "Blocked by 2 or more daughters"
                    if not heir.blocked:
                        fixed_shares[heir.name] = heir.share

        # ── PATERNAL GRANDFATHER ──
        elif rel == Relationship.PATERNAL_GRANDFATHER:
            if _has_male_descendants(heirs):
                heir.share = Fraction(1, 6)
                heir.basis = "Paternal grandfather gets 1/6 (like father) when male descendants exist"
                fixed_shares[heir.name] = heir.share
            elif _has_descendants(heirs):
                heir.share = Fraction(1, 6)
                heir.basis = "Paternal grandfather gets 1/6 fixed + residuary with only daughters"
                fixed_shares[heir.name] = heir.share
                residuary_heirs.append(heir)
            else:
                heir.basis = "Paternal grandfather is residuary heir (like father)"
                residuary_heirs.append(heir)

        # ── PATERNAL GRANDMOTHER ──
        elif rel == Relationship.PATERNAL_GRANDMOTHER:
            heir.share = Fraction(1, 6)
            heir.basis = "Grandmother gets 1/6"
            gm_count = _count(heirs, Relationship.PATERNAL_GRANDMOTHER) + _count(heirs, Relationship.MATERNAL_GRANDMOTHER)
            if gm_count > 1:
                heir.share = Fraction(1, 6) / gm_count
                heir.basis += f" (shared among {gm_count} grandmothers)"
            fixed_shares[heir.name] = heir.share

        # ── MATERNAL GRANDMOTHER ──
        elif rel == Relationship.MATERNAL_GRANDMOTHER:
            heir.share = Fraction(1, 6)
            heir.basis = "Grandmother gets 1/6"
            gm_count = _count(heirs, Relationship.PATERNAL_GRANDMOTHER) + _count(heirs, Relationship.MATERNAL_GRANDMOTHER)
            if gm_count > 1:
                heir.share = Fraction(1, 6) / gm_count
                heir.basis += f" (shared among {gm_count} grandmothers)"
            fixed_shares[heir.name] = heir.share

        # ── FULL BROTHER ──
        elif rel == Relationship.FULL_BROTHER:
            heir.basis = "Full brother is residuary heir (Asaba)"
            residuary_heirs.append(heir)

        # ── FULL SISTER ──
        elif rel == Relationship.FULL_SISTER:
            if _has(heirs, Relationship.FULL_BROTHER):
                heir.basis = "Full sister as residuary with full brother (2:1 ratio)"
                residuary_heirs.append(heir)
            elif _has_descendants(heirs):
                # In Hanafi: full sister becomes residuary with daughters
                heir.basis = "Full sister as residuary with daughters (Hanafi)"
                residuary_heirs.append(heir)
            else:
                sister_count = _count(heirs, Relationship.FULL_SISTER)
                if sister_count == 1:
                    heir.share = Fraction(1, 2)
                    heir.basis = "Quran 4:176 - Single full sister gets 1/2"
                else:
                    heir.share = Fraction(2, 3) / sister_count
                    heir.basis = f"Quran 4:176 - Full sisters share 2/3 ({sister_count} sisters)"
                fixed_shares[heir.name] = heir.share

        # ── PATERNAL HALF BROTHER ──
        elif rel == Relationship.PATERNAL_HALF_BROTHER:
            heir.basis = "Paternal half brother is residuary heir"
            residuary_heirs.append(heir)

        # ── PATERNAL HALF SISTER ──
        elif rel == Relationship.PATERNAL_HALF_SISTER:
            if _has(heirs, Relationship.PATERNAL_HALF_BROTHER):
                heir.basis = "Paternal half sister as residuary with paternal half brother (2:1)"
                residuary_heirs.append(heir)
            else:
                phs_count = _count(heirs, Relationship.PATERNAL_HALF_SISTER)
                full_sister_count = _count(heirs, Relationship.FULL_SISTER)
                if full_sister_count == 0:
                    if phs_count == 1:
                        heir.share = Fraction(1, 2)
                        heir.basis = "Paternal half sister gets 1/2 (no full sisters)"
                    else:
                        heir.share = Fraction(2, 3) / phs_count
                        heir.basis = f"Paternal half sisters share 2/3 ({phs_count})"
                elif full_sister_count == 1:
                    heir.share = Fraction(1, 6) / phs_count
                    heir.basis = "Paternal half sister gets 1/6 to complete 2/3 (with one full sister)"
                else:
                    heir.blocked = True
                    heir.blocked_by = "2+ full sisters"
                    heir.basis = "Blocked by 2 or more full sisters"
                if not heir.blocked:
                    fixed_shares[heir.name] = heir.share

        # ── MATERNAL HALF BROTHER / SISTER ──
        elif rel in (Relationship.MATERNAL_HALF_BROTHER, Relationship.MATERNAL_HALF_SISTER):
            mat_count = _count(heirs, Relationship.MATERNAL_HALF_BROTHER) + _count(heirs, Relationship.MATERNAL_HALF_SISTER)
            if mat_count == 1:
                heir.share = Fraction(1, 6)
                heir.basis = "Quran 4:12 - Single maternal half sibling gets 1/6"
            else:
                heir.share = Fraction(1, 3) / mat_count
                heir.basis = f"Quran 4:12 - Maternal half siblings share 1/3 equally ({mat_count})"
            fixed_shares[heir.name] = heir.share

        # ── DISTANT ASABA (Residuary) HEIRS ──
        elif rel == Relationship.FULL_NEPHEW:
            heir.basis = "Full nephew (full brother's son) is residuary heir"
            residuary_heirs.append(heir)
        elif rel == Relationship.PATERNAL_NEPHEW:
            heir.basis = "Paternal nephew (paternal brother's son) is residuary heir"
            residuary_heirs.append(heir)
        elif rel == Relationship.FULL_NEPHEWS_SON:
            heir.basis = "Full nephew's son (full brother's son's son) is residuary heir"
            residuary_heirs.append(heir)
        elif rel == Relationship.PATERNAL_NEPHEWS_SON:
            heir.basis = "Paternal nephew's son (paternal brother's son's son) is residuary heir"
            residuary_heirs.append(heir)
        elif rel == Relationship.FULL_PATERNAL_UNCLE:
            heir.basis = "Full paternal uncle (father's full brother) is residuary heir"
            residuary_heirs.append(heir)
        elif rel == Relationship.PATERNAL_PATERNAL_UNCLE:
            heir.basis = "Paternal paternal uncle (father's paternal brother) is residuary heir"
            residuary_heirs.append(heir)
        elif rel == Relationship.FULL_COUSIN:
            heir.basis = "Full cousin (father's full brother's son) is residuary heir"
            residuary_heirs.append(heir)
        elif rel == Relationship.PATERNAL_COUSIN:
            heir.basis = "Paternal cousin (father's paternal brother's son) is residuary heir"
            residuary_heirs.append(heir)
        elif rel == Relationship.FULL_COUSINS_SON:
            heir.basis = "Full cousin's son (father's full brother's son's son) is residuary heir"
            residuary_heirs.append(heir)
        elif rel == Relationship.PATERNAL_COUSINS_SON:
            heir.basis = "Paternal cousin's son (father's paternal brother's son's son) is residuary heir"
            residuary_heirs.append(heir)
        elif rel == Relationship.FULL_COUSINS_GRANDSON:
            heir.basis = "Full cousin's grandson (father's full brother's son's son's son) is residuary heir"
            residuary_heirs.append(heir)
        elif rel == Relationship.PATERNAL_COUSINS_GRANDSON:
            heir.basis = "Paternal cousin's grandson (father's paternal brother's son's son's son) is residuary heir"
            residuary_heirs.append(heir)

    # Step 4: Calculate total fixed shares
    total_fixed = sum(fixed_shares.values())

    # Step 5: Handle Awl (proportional reduction) if shares exceed estate
    awl_applied = False
    if total_fixed > Fraction(1):
        awl_applied = True
        for heir in heirs:
            if not heir.blocked and heir.share and heir.name in fixed_shares:
                heir.share = fixed_shares[heir.name] / total_fixed  # Proportional reduction
                heir.basis += f" [Awl applied - shares reduced proportionally, total was {total_fixed}]"
        # Residuary heirs who also have fixed shares already got their reduced share
        # Remove them from residuary since there's nothing left to distribute
        residuary_heirs = [h for h in residuary_heirs if h.name not in fixed_shares]

    # Step 6: Distribute residuary
    residuary_fraction = Fraction(1) - min(total_fixed, Fraction(1))
    if residuary_heirs and residuary_fraction > Fraction(0):
        _distribute_residuary_hanafi(residuary_heirs, residuary_fraction, heirs)

    # Step 7: Handle Radd (return excess to heirs) if no residuary and shares < estate
    radd_applied = False
    if not residuary_heirs and total_fixed < Fraction(1) and not awl_applied:
        radd_applied = True
        excess = Fraction(1) - total_fixed
        # Radd goes to all fixed share holders EXCEPT spouse
        radd_eligible = [h for h in heirs if not h.blocked and h.share
                         and h.relationship not in (Relationship.HUSBAND, Relationship.WIFE)]
        radd_total = sum(h.share for h in radd_eligible)
        if radd_total > 0:
            for heir in radd_eligible:
                radd_portion = excess * (heir.share / radd_total)
                heir.share += radd_portion
                heir.basis += " [Radd - excess returned proportionally]"

    # Step 8: Calculate amounts
    for heir in heirs:
        if heir.share and not heir.blocked:
            heir.share_amount = float(heir.share) * distributable

    return _build_result(heirs, total_estate, debts, actual_bequest, distributable,
                         "Islamic (Sunni Hanafi)", awl_applied, radd_applied)


def _apply_hanafi_blocking(heirs: list[Heir]):
    """Apply Hanafi blocking (Hajb) rules."""
    # Son blocks: son's son, son's daughter
    if _has(heirs, Relationship.SON):
        for h in heirs:
            if h.relationship == Relationship.SONS_SON:
                h.blocked = True
                h.blocked_by = "Son"
                h.basis = "Blocked by Son — In Hanafi fiqh, a closer male descendant (son) excludes a more distant male descendant (grandson through son). The son inherits as a primary residuary (Asaba), leaving no share for the grandson."
            # Son's daughter is NOT blocked by son - she becomes residuary with son

    # Father blocks: paternal grandfather, all siblings, and all distant asaba
    _distant_asaba = [
        Relationship.FULL_NEPHEW, Relationship.PATERNAL_NEPHEW,
        Relationship.FULL_NEPHEWS_SON, Relationship.PATERNAL_NEPHEWS_SON,
        Relationship.FULL_PATERNAL_UNCLE, Relationship.PATERNAL_PATERNAL_UNCLE,
        Relationship.FULL_COUSIN, Relationship.PATERNAL_COUSIN,
        Relationship.FULL_COUSINS_SON, Relationship.PATERNAL_COUSINS_SON,
        Relationship.FULL_COUSINS_GRANDSON, Relationship.PATERNAL_COUSINS_GRANDSON,
    ]
    if _has(heirs, Relationship.FATHER):
        blocking_targets = [
            Relationship.PATERNAL_GRANDFATHER,
            Relationship.FULL_BROTHER, Relationship.FULL_SISTER,
            Relationship.PATERNAL_HALF_BROTHER, Relationship.PATERNAL_HALF_SISTER,
            Relationship.MATERNAL_HALF_BROTHER, Relationship.MATERNAL_HALF_SISTER,
        ] + _distant_asaba
        _father_block_reasons = {
            Relationship.PATERNAL_GRANDFATHER: "Blocked by Father — The father is a closer ascendant than the paternal grandfather. In Hanafi fiqh, a nearer male ascendant excludes the more distant one from inheritance.",
            Relationship.FULL_BROTHER: "Blocked by Father — In Hanafi fiqh, the father excludes all siblings (full, paternal, and maternal) from inheritance. The father takes precedence as both a fixed-share and residuary heir.",
            Relationship.FULL_SISTER: "Blocked by Father — In Hanafi fiqh, the father excludes all siblings from inheritance. Sisters cannot inherit alongside the father.",
            Relationship.PATERNAL_HALF_BROTHER: "Blocked by Father — In Hanafi fiqh, the father excludes all half-siblings. Paternal half-brothers are blocked because the father is a closer agnatic relative.",
            Relationship.PATERNAL_HALF_SISTER: "Blocked by Father — In Hanafi fiqh, the father excludes all half-siblings. Paternal half-sisters cannot inherit when the father is alive.",
            Relationship.MATERNAL_HALF_BROTHER: "Blocked by Father — In Hanafi fiqh, the father (or any male ascendant) completely excludes maternal half-siblings from inheritance (Quran 4:12).",
            Relationship.MATERNAL_HALF_SISTER: "Blocked by Father — In Hanafi fiqh, the father (or any male ascendant) completely excludes maternal half-siblings from inheritance (Quran 4:12).",
        }
        _default_father_reason = "Blocked by Father — In Hanafi fiqh, the father excludes more distant agnatic relatives (nephews, uncles, cousins) from inheritance. The father is a closer residuary heir."
        for h in heirs:
            if h.relationship in blocking_targets:
                h.blocked = True
                h.blocked_by = "Father"
                h.basis = _father_block_reasons.get(h.relationship, _default_father_reason)

    # Mother blocks: paternal grandmother, maternal grandmother
    if _has(heirs, Relationship.MOTHER):
        for h in heirs:
            if h.relationship in (Relationship.PATERNAL_GRANDMOTHER, Relationship.MATERNAL_GRANDMOTHER):
                h.blocked = True
                h.blocked_by = "Mother"
                h.basis = "Blocked by Mother — In Hanafi fiqh, the mother (a nearer female ascendant) excludes all grandmothers from inheritance. The grandmother's fixed share of 1/6 is only available when the mother is not alive."

    # Son/son's son blocks: all siblings and all distant asaba
    if _has_male_descendants(heirs):
        sibling_rels = [
            Relationship.FULL_BROTHER, Relationship.FULL_SISTER,
            Relationship.PATERNAL_HALF_BROTHER, Relationship.PATERNAL_HALF_SISTER,
            Relationship.MATERNAL_HALF_BROTHER, Relationship.MATERNAL_HALF_SISTER,
        ] + _distant_asaba
        for h in heirs:
            if h.relationship in sibling_rels:
                h.blocked = True
                h.blocked_by = "Son/Son's son"
                if h.relationship in (Relationship.MATERNAL_HALF_BROTHER, Relationship.MATERNAL_HALF_SISTER):
                    h.basis = "Blocked by Son/Son's son — Maternal half-siblings are excluded when the deceased has any descendants (Quran 4:12). They only inherit when there are no children, grandchildren, father, or grandfather."
                elif h.relationship in (Relationship.FULL_BROTHER, Relationship.FULL_SISTER, Relationship.PATERNAL_HALF_BROTHER, Relationship.PATERNAL_HALF_SISTER):
                    h.basis = "Blocked by Son/Son's son — In Hanafi fiqh, male descendants (son or son's son) are stronger residuary heirs (Asaba) than siblings. Siblings can only inherit when there are no male descendants."
                else:
                    h.basis = "Blocked by Son/Son's son — Male descendants exclude all distant agnatic relatives (nephews, uncles, cousins) from inheritance as they are closer residuary heirs."

    # Descendants block maternal half siblings
    if _has_descendants(heirs):
        for h in heirs:
            if h.relationship in (Relationship.MATERNAL_HALF_BROTHER, Relationship.MATERNAL_HALF_SISTER):
                h.blocked = True
                h.blocked_by = "Descendants"
                h.basis = "Blocked by Descendants — Maternal half-siblings are completely excluded when the deceased has any children or grandchildren through sons (Quran 4:12). They only inherit in the absence of all descendants, father, and grandfather."

    # Full brother blocks: paternal half siblings + all distant asaba
    if _has(heirs, Relationship.FULL_BROTHER):
        blocked_by_fb = [
            Relationship.PATERNAL_HALF_BROTHER, Relationship.PATERNAL_HALF_SISTER,
        ] + _distant_asaba
        for h in heirs:
            if h.relationship in blocked_by_fb:
                h.blocked = True
                h.blocked_by = "Full brother"
                if h.relationship in (Relationship.PATERNAL_HALF_BROTHER, Relationship.PATERNAL_HALF_SISTER):
                    h.basis = "Blocked by Full Brother — A full brother (sharing both parents with the deceased) is a stronger agnatic heir than a paternal half-brother/sister (sharing only the father). The closer blood tie gives full siblings priority."
                else:
                    h.basis = "Blocked by Full Brother — The full brother is a closer residuary heir (Asaba) than distant agnatic relatives. In Hanafi fiqh, closer Asaba exclude more distant ones from inheritance."

    # Paternal half brother blocks: all distant asaba (nephews, uncles, cousins)
    if _has(heirs, Relationship.PATERNAL_HALF_BROTHER):
        for h in heirs:
            if h.relationship in _distant_asaba:
                h.blocked = True
                h.blocked_by = "Paternal half brother"
                h.basis = "Blocked by Paternal Half Brother — The paternal half-brother is a closer residuary heir than distant agnatic relatives (nephews, uncles, cousins). In Hanafi fiqh, closer Asaba always exclude more distant ones."

    # Cascading blocks among distant asaba (each blocks all below it in priority)
    _distant_priority = [
        Relationship.FULL_NEPHEW,
        Relationship.PATERNAL_NEPHEW,
        Relationship.FULL_NEPHEWS_SON,
        Relationship.PATERNAL_NEPHEWS_SON,
        Relationship.FULL_PATERNAL_UNCLE,
        Relationship.PATERNAL_PATERNAL_UNCLE,
        Relationship.FULL_COUSIN,
        Relationship.PATERNAL_COUSIN,
        Relationship.FULL_COUSINS_SON,
        Relationship.PATERNAL_COUSINS_SON,
        Relationship.FULL_COUSINS_GRANDSON,
        Relationship.PATERNAL_COUSINS_GRANDSON,
    ]
    for i, rel in enumerate(_distant_priority):
        if _has(heirs, rel):
            blocker_label = rel.replace('_', ' ').title()
            for h in heirs:
                if h.relationship in _distant_priority[i + 1:] and not h.blocked:
                    h.blocked = True
                    h.blocked_by = blocker_label
                    h.basis = f"Blocked by {blocker_label} — In Hanafi fiqh, distant agnatic relatives (Asaba) inherit in a strict priority order. The {blocker_label} is a closer agnatic heir and therefore excludes all more distant relatives from inheriting."
            break  # Only the highest priority distant asaba does the blocking


def _distribute_residuary_hanafi(residuary_heirs: list[Heir], residuary: Fraction, all_heirs: list[Heir]):
    """Distribute residuary share among Asaba heirs in Hanafi fiqh."""
    # Group residuary heirs by priority
    # Priority: 1) Sons/Daughters, 2) Son's sons/daughters, 3) Father, 4) Grandfather,
    #           5) Full brothers/sisters, 6) Paternal half brothers/sisters

    priority_groups = [
        ([Relationship.SON, Relationship.DAUGHTER], "children"),
        ([Relationship.SONS_SON, Relationship.SONS_DAUGHTER], "grandchildren"),
        ([Relationship.FATHER], "father"),
        ([Relationship.PATERNAL_GRANDFATHER], "grandfather"),
        ([Relationship.FULL_BROTHER, Relationship.FULL_SISTER], "full_siblings"),
        ([Relationship.PATERNAL_HALF_BROTHER, Relationship.PATERNAL_HALF_SISTER], "paternal_half_siblings"),
        ([Relationship.FULL_NEPHEW], "full_nephews"),
        ([Relationship.PATERNAL_NEPHEW], "paternal_nephews"),
        ([Relationship.FULL_NEPHEWS_SON], "full_nephews_sons"),
        ([Relationship.PATERNAL_NEPHEWS_SON], "paternal_nephews_sons"),
        ([Relationship.FULL_PATERNAL_UNCLE], "full_paternal_uncles"),
        ([Relationship.PATERNAL_PATERNAL_UNCLE], "paternal_paternal_uncles"),
        ([Relationship.FULL_COUSIN], "full_cousins"),
        ([Relationship.PATERNAL_COUSIN], "paternal_cousins"),
        ([Relationship.FULL_COUSINS_SON], "full_cousins_sons"),
        ([Relationship.PATERNAL_COUSINS_SON], "paternal_cousins_sons"),
        ([Relationship.FULL_COUSINS_GRANDSON], "full_cousins_grandsons"),
        ([Relationship.PATERNAL_COUSINS_GRANDSON], "paternal_cousins_grandsons"),
    ]

    for rels, _group_name in priority_groups:
        group = [h for h in residuary_heirs if h.relationship in rels]
        if not group:
            continue

        # Calculate total shares using 2:1 male:female ratio
        total_parts = Fraction(0)
        for h in group:
            if h.gender == Gender.MALE:
                total_parts += Fraction(2) * h.count
            else:
                total_parts += Fraction(1) * h.count

        if total_parts == 0:
            continue

        for h in group:
            if h.gender == Gender.MALE:
                per_person = (residuary * Fraction(2)) / total_parts
            else:
                per_person = (residuary * Fraction(1)) / total_parts

            if h.share:
                h.share += per_person  # Add to existing fixed share (e.g., father's 1/6)
            else:
                h.share = per_person

        # Only highest priority group gets residuary
        break


# ─── SHIA (JAFARI) INHERITANCE ───────────────────────────────────────────

def calculate_islamic_shia(heirs: list[Heir], total_estate: float, debts: float = 0, bequests: float = 0) -> dict:
    """
    Calculate inheritance according to Shia (Ithna Ashari / Jafari) fiqh.
    Key differences from Sunni:
    - No Awl (proportional reduction) - instead spouse share is protected, others reduced
    - Daughters can block siblings (unlike Sunni where they become residuary together)
    - Different treatment of grandfather with siblings
    """
    net_estate = total_estate - debts
    max_bequest = net_estate / 3
    actual_bequest = min(bequests, max_bequest)
    distributable = net_estate - actual_bequest

    # Shia uses 3 classes of heirs:
    # Class 1: Parents + Children (and their descendants)
    # Class 2: Grandparents + Siblings (and their descendants)
    # Class 3: Uncles/Aunts (and their descendants)
    # Lower class only inherits if no one from higher class exists

    _apply_shia_blocking(heirs)

    for heir in heirs:
        if heir.blocked:
            continue

        rel = heir.relationship

        if rel == Relationship.HUSBAND:
            if _has_descendants(heirs):
                heir.share = Fraction(1, 4)
                heir.basis = "Husband gets 1/4 with children (Shia law)"
            else:
                heir.share = Fraction(1, 2)
                heir.basis = "Husband gets 1/2 without children (Shia law)"

        elif rel == Relationship.WIFE:
            if _has_descendants(heirs):
                heir.share = Fraction(1, 8)
                heir.basis = "Wife gets 1/8 with children (Shia law)"
            else:
                heir.share = Fraction(1, 4)
                heir.basis = "Wife gets 1/4 without children (Shia law)"
            wife_count = _count(heirs, Relationship.WIFE)
            if wife_count > 1:
                heir.share = heir.share / wife_count

        elif rel == Relationship.FATHER:
            if _has(heirs, Relationship.SON):
                heir.share = Fraction(1, 6)
                heir.basis = "Father gets 1/6 with son (Shia law)"
            elif _has(heirs, Relationship.DAUGHTER):
                heir.share = Fraction(1, 6)
                heir.basis = "Father gets 1/6 fixed + residuary with daughter(s) (Shia law)"
            else:
                heir.share = Fraction(1)  # Will be adjusted
                heir.basis = "Father inherits remainder (Shia law)"

        elif rel == Relationship.MOTHER:
            if _has_descendants(heirs) or _siblings_count(heirs) >= 2:
                heir.share = Fraction(1, 6)
                heir.basis = "Mother gets 1/6 with children or 2+ siblings (Shia law)"
            else:
                heir.share = Fraction(1, 3)
                heir.basis = "Mother gets 1/3 without children (Shia law)"

        elif rel == Relationship.SON:
            heir.basis = "Son inherits as residuary (Shia law)"
            # Will be calculated after fixed shares

        elif rel == Relationship.DAUGHTER:
            if not _has(heirs, Relationship.SON):
                d_count = _count(heirs, Relationship.DAUGHTER)
                if d_count == 1:
                    heir.share = Fraction(1, 2)
                    heir.basis = "Single daughter gets 1/2 (Shia law)"
                else:
                    heir.share = Fraction(2, 3) / d_count
                    heir.basis = f"Daughters share 2/3 ({d_count} daughters) (Shia law)"
            else:
                heir.basis = "Daughter inherits with son, 2:1 ratio (Shia law)"

        elif rel in (Relationship.FULL_BROTHER, Relationship.FULL_SISTER,
                     Relationship.PATERNAL_HALF_BROTHER, Relationship.PATERNAL_HALF_SISTER,
                     Relationship.MATERNAL_HALF_BROTHER, Relationship.MATERNAL_HALF_SISTER):
            heir.basis = f"{rel} inherits in Shia Class 2"

    # Calculate residuary for sons/daughters
    fixed_total = sum(h.share for h in heirs if h.share and not h.blocked
                      and h.relationship not in (Relationship.SON, Relationship.DAUGHTER))

    sons = _get(heirs, Relationship.SON)
    daughters = _get(heirs, Relationship.DAUGHTER)
    if sons:
        residuary = Fraction(1) - min(fixed_total, Fraction(1))
        total_parts = sum(Fraction(2) * h.count for h in sons) + sum(Fraction(1) * h.count for h in daughters)
        if total_parts > 0:
            for h in sons:
                h.share = (residuary * Fraction(2) * h.count) / total_parts / h.count
            for h in daughters:
                h.share = (residuary * Fraction(1) * h.count) / total_parts / h.count
    elif not daughters and not _has(heirs, Relationship.SON):
        # Father gets remainder
        father = _get(heirs, Relationship.FATHER)
        if father:
            used = sum(h.share for h in heirs if h.share and not h.blocked and h.relationship != Relationship.FATHER)
            father[0].share = Fraction(1) - min(used, Fraction(1))

    # Radd for daughters (Shia: return to daughters, not spouse)
    total_shares = sum(h.share for h in heirs if h.share and not h.blocked)
    if total_shares < Fraction(1):
        excess = Fraction(1) - total_shares
        non_spouse = [h for h in heirs if h.share and not h.blocked
                      and h.relationship not in (Relationship.HUSBAND, Relationship.WIFE)]
        ns_total = sum(h.share for h in non_spouse)
        if ns_total > 0:
            for h in non_spouse:
                radd = excess * (h.share / ns_total)
                h.share += radd
                h.basis += " [Radd applied]"

    for heir in heirs:
        if heir.share and not heir.blocked:
            heir.share_amount = float(heir.share) * distributable

    return _build_result(heirs, total_estate, debts, actual_bequest, distributable,
                         "Islamic (Shia/Jafari)", False, False)


def _apply_shia_blocking(heirs: list[Heir]):
    """Shia blocking: Class system - higher class blocks lower entirely."""
    has_class1 = _has_any(heirs, [
        Relationship.FATHER, Relationship.MOTHER,
        Relationship.SON, Relationship.DAUGHTER,
        Relationship.SONS_SON, Relationship.SONS_DAUGHTER,
    ])

    class2_rels = [
        Relationship.FULL_BROTHER, Relationship.FULL_SISTER,
        Relationship.PATERNAL_HALF_BROTHER, Relationship.PATERNAL_HALF_SISTER,
        Relationship.MATERNAL_HALF_BROTHER, Relationship.MATERNAL_HALF_SISTER,
        Relationship.PATERNAL_GRANDFATHER, Relationship.PATERNAL_GRANDMOTHER,
        Relationship.MATERNAL_GRANDMOTHER,
        Relationship.FULL_NEPHEW, Relationship.PATERNAL_NEPHEW,
        Relationship.FULL_NEPHEWS_SON, Relationship.PATERNAL_NEPHEWS_SON,
        Relationship.FULL_PATERNAL_UNCLE, Relationship.PATERNAL_PATERNAL_UNCLE,
        Relationship.FULL_COUSIN, Relationship.PATERNAL_COUSIN,
        Relationship.FULL_COUSINS_SON, Relationship.PATERNAL_COUSINS_SON,
        Relationship.FULL_COUSINS_GRANDSON, Relationship.PATERNAL_COUSINS_GRANDSON,
    ]

    if has_class1:
        for h in heirs:
            if h.relationship in class2_rels:
                h.blocked = True
                h.blocked_by = "Class 1 heirs exist (Shia law)"
                h.basis = f"Blocked — In Shia (Jafari) fiqh, heirs are divided into 3 classes. Class 1 (parents, children, grandchildren) entirely excludes Class 2 (siblings, grandparents, nephews) and Class 3 (uncles, cousins). Since Class 1 heirs are present, {h.name} ({h.relationship.replace('_', ' ')}) receives no share."


# ─── CHRISTIAN LAW (Succession Act 1925) ─────────────────────────────────

def calculate_christian(heirs: list[Heir], total_estate: float, debts: float = 0, bequests: float = 0) -> dict:
    """
    Calculate inheritance under the Succession Act 1925 (applicable to Christians in Pakistan).
    - Equal shares for sons and daughters (no gender distinction)
    - Spouse gets 1/3 if children exist, 1/2 if no children
    """
    net_estate = total_estate - debts
    actual_bequest = min(bequests, net_estate)  # No 1/3 limit for non-Muslims
    distributable = net_estate - actual_bequest

    children = [h for h in heirs if h.relationship in (Relationship.SON, Relationship.DAUGHTER)]
    spouse = [h for h in heirs if h.relationship in (Relationship.HUSBAND, Relationship.WIFE)]
    parents = [h for h in heirs if h.relationship in (Relationship.FATHER, Relationship.MOTHER)]
    siblings = [h for h in heirs if h.relationship in (
        Relationship.FULL_BROTHER, Relationship.FULL_SISTER,
        Relationship.PATERNAL_HALF_BROTHER, Relationship.PATERNAL_HALF_SISTER,
    )]

    if children:
        # Spouse gets 1/3, children share 2/3 equally
        total_children = sum(h.count for h in children)
        for h in spouse:
            h.share = Fraction(1, 3)
            h.basis = "Succession Act 1925 S.33 - Spouse gets 1/3 when children exist"
            spouse_count = sum(s.count for s in spouse)
            if spouse_count > 1:
                h.share = Fraction(1, 3) / spouse_count

        child_share = Fraction(2, 3) / total_children
        for h in children:
            h.share = child_share
            h.basis = f"Succession Act 1925 S.35 - Children share 2/3 equally ({total_children} children)"

        # Parents and siblings are excluded when children exist
        for h in parents + siblings:
            h.blocked = True
            h.blocked_by = "Children exist"
            h.basis = f"Blocked — Under the Succession Act 1925 (S.33-35), when the deceased has children, the estate is divided between the spouse (1/3) and children (2/3 equally). Parents and siblings do not inherit when children are alive."

    elif spouse and (parents or siblings):
        # Spouse gets 1/2, rest shared by kindred
        for h in spouse:
            h.share = Fraction(1, 2)
            h.basis = "Succession Act 1925 S.33 - Spouse gets 1/2 when no children"
            spouse_count = sum(s.count for s in spouse)
            if spouse_count > 1:
                h.share = Fraction(1, 2) / spouse_count

        kindred = parents + siblings
        total_kindred = sum(h.count for h in kindred)
        if total_kindred > 0:
            kindred_share = Fraction(1, 2) / total_kindred
            for h in kindred:
                h.share = kindred_share
                h.basis = f"Succession Act 1925 S.33 - Kindred share 1/2 equally"

    elif spouse:
        # Only spouse, gets everything
        for h in spouse:
            h.share = Fraction(1)
            h.basis = "Succession Act 1925 - Spouse inherits entire estate (no other heirs)"

    elif parents:
        # No spouse, no children - parents inherit
        total_p = sum(h.count for h in parents)
        for h in parents:
            h.share = Fraction(1) / total_p
            h.basis = f"Succession Act 1925 - Parents share estate equally"

    elif siblings:
        total_s = sum(h.count for h in siblings)
        for h in siblings:
            h.share = Fraction(1) / total_s
            h.basis = "Succession Act 1925 - Siblings share estate equally"

    for heir in heirs:
        if heir.share and not heir.blocked:
            heir.share_amount = float(heir.share) * distributable

    return _build_result(heirs, total_estate, debts, actual_bequest, distributable,
                         "Christian (Succession Act 1925)", False, False)


# ─── HINDU LAW ────────────────────────────────────────────────────────────

def calculate_hindu(heirs: list[Heir], total_estate: float, debts: float = 0, bequests: float = 0) -> dict:
    """
    Calculate inheritance under Hindu law as applicable in Pakistan.
    Based on Hindu Succession Act principles and customary law.
    Class I heirs share equally regardless of gender.
    """
    net_estate = total_estate - debts
    actual_bequest = min(bequests, net_estate)
    distributable = net_estate - actual_bequest

    # Class I heirs: sons, daughters, widow, mother
    class1 = [h for h in heirs if h.relationship in (
        Relationship.SON, Relationship.DAUGHTER,
        Relationship.WIFE, Relationship.MOTHER
    )]

    # Class II heirs: father, siblings, grandparents
    class2 = [h for h in heirs if h.relationship in (
        Relationship.FATHER, Relationship.FULL_BROTHER, Relationship.FULL_SISTER,
        Relationship.PATERNAL_GRANDFATHER, Relationship.PATERNAL_GRANDMOTHER,
    )]

    if class1:
        total_members = sum(h.count for h in class1)
        per_share = Fraction(1) / total_members
        for h in class1:
            h.share = per_share
            h.basis = f"Hindu Succession - Class I heirs share equally ({total_members} members)"
        for h in class2:
            h.blocked = True
            h.blocked_by = "Class I heirs exist"
            h.basis = f"Blocked — Under Hindu Succession Law, Class I heirs (spouse, children, mother) have absolute priority. Class II heirs (father, siblings, grandparents) are completely excluded when any Class I heir exists."
    elif class2:
        total_members = sum(h.count for h in class2)
        per_share = Fraction(1) / total_members
        for h in class2:
            h.share = per_share
            h.basis = f"Hindu Succession - Class II heirs share equally ({total_members} members)"
    else:
        # Husband inherits in absence of Class I and II
        husband = _get(heirs, Relationship.HUSBAND)
        if husband:
            husband[0].share = Fraction(1)
            husband[0].basis = "Hindu Succession - Husband inherits in absence of other heirs"

    for heir in heirs:
        if heir.share and not heir.blocked:
            heir.share_amount = float(heir.share) * distributable

    return _build_result(heirs, total_estate, debts, actual_bequest, distributable,
                         "Hindu Law", False, False)


# ─── SIKH LAW ─────────────────────────────────────────────────────────────

def calculate_sikh(heirs: list[Heir], total_estate: float, debts: float = 0, bequests: float = 0) -> dict:
    """
    Calculate inheritance under Sikh customary law / Succession Act 1925.
    In Pakistan, Sikhs generally follow the Succession Act 1925 or customary law.
    Equal distribution among children regardless of gender. Similar to Christian law.
    """
    # Sikh inheritance in Pakistan follows similar rules to Succession Act
    return calculate_christian(heirs, total_estate, debts, bequests)


# ─── RESULT BUILDER ──────────────────────────────────────────────────────

def _build_result(heirs, total_estate, debts, bequests, distributable, law_system, awl, radd):
    active_heirs = [h for h in heirs if not h.blocked]
    blocked_heirs = [h for h in heirs if h.blocked]

    total_distributed = sum(h.share_amount for h in active_heirs)
    undistributed = distributable - total_distributed

    return {
        "law_system": law_system,
        "total_estate": round(total_estate, 2),
        "debts": round(debts, 2),
        "bequests": round(bequests, 2),
        "distributable_estate": round(distributable, 2),
        "total_distributed": round(total_distributed, 2),
        "undistributed": round(abs(undistributed), 2),
        "awl_applied": awl,
        "radd_applied": radd,
        "heirs": [h.to_dict() for h in active_heirs],
        "blocked_heirs": [h.to_dict() for h in blocked_heirs],
        "summary": {
            "total_heirs": len(active_heirs),
            "total_blocked": len(blocked_heirs),
        }
    }


# ─── MAIN DISPATCHER ─────────────────────────────────────────────────────

def calculate_inheritance(
    religion: str,
    heirs_data: list[dict],
    total_estate: float,
    debts: float = 0,
    bequests: float = 0,
) -> dict:
    """
    Main entry point for inheritance calculation.

    Args:
        religion: One of 'sunni_hanafi', 'shia', 'christian', 'hindu', 'sikh'
        heirs_data: List of dicts with keys: name, relationship, gender, count
        total_estate: Total value of estate
        debts: Outstanding debts to deduct
        bequests: Bequests/wasiyyah amount

    Returns:
        Dict with full inheritance breakdown
    """
    heirs = [
        Heir(
            name=h["name"],
            relationship=h["relationship"],
            gender=h.get("gender", "male"),
            count=h.get("count", 1),
        )
        for h in heirs_data
    ]

    calculators = {
        Religion.SUNNI_HANAFI: calculate_islamic_hanafi,
        Religion.SHIA: calculate_islamic_shia,
        Religion.CHRISTIAN: calculate_christian,
        Religion.HINDU: calculate_hindu,
        Religion.SIKH: calculate_sikh,
    }

    calculator = calculators.get(religion)
    if not calculator:
        raise ValueError(f"Unsupported religion/law system: {religion}. Supported: {list(calculators.keys())}")

    return calculator(heirs, total_estate, debts, bequests)
