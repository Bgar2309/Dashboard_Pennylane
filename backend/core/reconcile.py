"""Lettrage maison (rapprochement débit/crédit) d'UN compte client. Aucun I/O.

Module pur : pas de réseau, pas de DB, aucune dépendance à integration/.
Il prend les lignes brutes normalisées d'un compte client et rend les créances
résiduelles à relancer après imputation FIFO des paiements sur les factures.

Le problème métier résolu ici est le DOUBLE COMPTAGE des reports « A-Nouveau ».
Quand une fenêtre d'analyse démarre au 1er janvier d'une année N, l'écriture
d'A-Nouveau posée au 1er janvier de l'année N+1 reprend, sous forme de solde
d'ouverture, des factures de fin N qui sont DÉJÀ présentes dans la fenêtre comme
débits. Les compter à nouveau gonfle artificiellement l'encours. On neutralise
ces doublons (cf. reconcile_account, étape 3).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

# Tolérance d'arrondi : un reliquat <= 0,005 € est considéré comme nul.
_ZERO_TOLERANCE = Decimal("0.005")
# Tolérance de rapprochement A-Nouveau / facture : ±1,00 €.
_AN_MATCH_TOLERANCE = Decimal("1.00")


@dataclass
class RawLine:
    """Ligne d'écriture brute d'un compte client, normalisée."""
    id: int
    date: date
    debit: Decimal       # >= 0
    credit: Decimal      # >= 0
    label: str
    is_opening_balance: bool   # True si A-Nouveau (report d'ouverture)
    invoice_number: str | None  # numéro extrait si dispo, sinon None


@dataclass
class OpenItem:
    """Une créance résiduelle après rapprochement (= à relancer)."""
    source_line_id: int
    date: date
    amount_original: Decimal     # montant débit d'origine
    amount_remaining: Decimal    # reliquat après imputation FIFO
    label: str
    invoice_number: str | None


def _sort_key(line: RawLine) -> tuple[date, int, int]:
    """Tri par date croissante ; à date égale, débit avant crédit.

    Le second critère (0 pour un débit, 1 pour un crédit) garantit qu'à date
    égale on présente d'abord la facture puis le paiement ; ``id`` départage le
    reste de façon déterministe.
    """
    is_credit = 1 if line.credit > line.debit else 0
    return (line.date, is_credit, line.id)


def reconcile_account(
    lines: list[RawLine],
    window_start: date,
) -> list[OpenItem]:
    """Rapproche débit/crédit d'UN compte client et rend les créances
    résiduelles (reliquats > 0).

    Algorithme :

    1. Tri des lignes par date croissante (à date égale : débit avant crédit).

    2. Neutralisation des annulations : une facture (débit D, date T) et sa
       contre-passation (crédit C == D, MÊME date T) s'annulent ; on retire la
       paire avant tout le reste. Au plus une annulation appariée par facture.

    3. Anti-doublon A-Nouveau : pour chaque ligne A-Nouveau, on cherche s'il
       existe AVANT sa date une ou plusieurs lignes débitrices non-A-Nouveau
       dont la somme des montants correspond (à ±1,00 €) au montant de
       l'A-Nouveau. Si oui, l'A-Nouveau n'est qu'un report d'une facture déjà
       présente dans la fenêtre : on l'EXCLUT (ni débit, ni imputable) pour ne
       pas double-compter. Sinon, on le conserve comme une créance « Solde
       antérieur » ordinaire.

       Justification : un A-Nouveau LÉGITIME représente un solde réellement
       antérieur à la fenêtre d'analyse, donc une créance dont la facture
       d'origine est hors fenêtre — elle n'apparaît donc PAS comme débit dans
       ``lines``. À l'inverse, un A-Nouveau dont le montant retombe exactement
       sur des factures déjà présentes ne fait que recopier l'encours de
       clôture de l'exercice précédent : le garder reviendrait à compter deux
       fois les mêmes factures.

    4. Imputation FIFO : sur les débits restants (du plus ancien au plus
       récent), on impute le total des crédits restants. Chaque débit dont le
       reliquat dépasse la tolérance d'arrondi (0,005 €) devient un OpenItem.

    Un A-Nouveau exclu à l'étape 3 n'est JAMAIS rendu comme OpenItem.

    Args:
        lines: lignes brutes normalisées du compte client.
        window_start: début de la fenêtre d'analyse (1er janvier en pratique).
            Conservé pour la sémantique métier et l'usage par l'appelant ;
            l'anti-doublon (étape 3) raisonne sur l'antériorité relative des
            lignes, pas sur cette borne.

    Returns:
        La liste des créances résiduelles, triées par date croissante.
    """
    ordered = sorted(lines, key=_sort_key)

    survivors = _neutralize_cancellations(ordered)
    debit_lines, excluded_ids = _flag_duplicate_openings(survivors)

    # Total des crédits restants (hors lignes neutralisées à l'étape 2).
    total_credit = sum(
        (ln.credit for ln in survivors if ln.credit > ln.debit),
        Decimal("0"),
    )

    return _impute_fifo(debit_lines, total_credit)


def _neutralize_cancellations(ordered: list[RawLine]) -> list[RawLine]:
    """Retire les paires facture / contre-passation (même date, même montant).

    Une facture est un débit non-A-Nouveau ; sa contre-passation est un crédit
    de montant égal à la même date. Chaque facture est appariée à au plus une
    contre-passation.
    """
    # Crédits disponibles pour servir de contre-passation, groupés par (date).
    credits = [
        ln for ln in ordered if ln.credit > ln.debit
    ]
    used_credit_ids: set[int] = set()
    removed_ids: set[int] = set()

    for line in ordered:
        is_debit = line.debit > line.credit
        if not is_debit or line.is_opening_balance:
            continue
        for credit in credits:
            if credit.id in used_credit_ids:
                continue
            if credit.date == line.date and credit.credit == line.debit:
                used_credit_ids.add(credit.id)
                removed_ids.add(line.id)
                removed_ids.add(credit.id)
                break

    return [ln for ln in ordered if ln.id not in removed_ids]


def _flag_duplicate_openings(
    survivors: list[RawLine],
) -> tuple[list[RawLine], set[int]]:
    """Sépare les débits à imputer en excluant les A-Nouveau doublons.

    Retourne (débits retenus triés du plus ancien au plus récent, ids exclus).
    """
    excluded_ids: set[int] = set()
    # Débits non-A-Nouveau « réels » servant de référence pour le matching ;
    # un débit ne peut adosser qu'une seule exclusion d'A-Nouveau.
    claimed_ids: set[int] = set()

    openings = [ln for ln in survivors if ln.is_opening_balance]
    real_debits = [
        ln for ln in survivors
        if ln.debit > ln.credit and not ln.is_opening_balance
    ]

    for opening in openings:
        candidates = [
            ln for ln in real_debits
            if ln.date < opening.date and ln.id not in claimed_ids
        ]
        matched = _find_matching_subset(candidates, opening.debit)
        if matched is not None:
            excluded_ids.add(opening.id)
            claimed_ids.update(ln.id for ln in matched)

    # Débits retenus : factures réelles + A-Nouveau légitimes (non exclus).
    debit_lines = [
        ln for ln in survivors
        if ln.debit > ln.credit and ln.id not in excluded_ids
    ]
    debit_lines.sort(key=_sort_key)
    return debit_lines, excluded_ids


def _find_matching_subset(
    candidates: list[RawLine],
    target: Decimal,
) -> list[RawLine] | None:
    """Cherche un sous-ensemble de débits dont la somme ≈ target (±1,00 €).

    On privilégie d'abord une correspondance sur une seule ligne (cas courant :
    l'A-Nouveau reprend une unique facture), puis sur des paires. On évite une
    recherche combinatoire complète : un report d'ouverture correspond en
    pratique à une, parfois deux, factures de fin d'exercice.
    """
    # 1 ligne.
    for ln in candidates:
        if abs(ln.debit - target) <= _AN_MATCH_TOLERANCE:
            return [ln]
    # 2 lignes.
    for i, a in enumerate(candidates):
        for b in candidates[i + 1:]:
            if abs(a.debit + b.debit - target) <= _AN_MATCH_TOLERANCE:
                return [a, b]
    return None


def _impute_fifo(
    debit_lines: list[RawLine],
    total_credit: Decimal,
) -> list[OpenItem]:
    """Impute le total des crédits sur les débits, du plus ancien au plus récent.

    Chaque débit dont le reliquat dépasse la tolérance d'arrondi devient un
    OpenItem (``amount_remaining`` = reliquat).
    """
    remaining_credit = total_credit
    open_items: list[OpenItem] = []

    for line in debit_lines:
        applied = min(remaining_credit, line.debit)
        remaining_credit -= applied
        residual = line.debit - applied
        if residual > _ZERO_TOLERANCE:
            open_items.append(
                OpenItem(
                    source_line_id=line.id,
                    date=line.date,
                    amount_original=line.debit,
                    amount_remaining=residual,
                    label=line.label,
                    invoice_number=line.invoice_number,
                )
            )

    return open_items
