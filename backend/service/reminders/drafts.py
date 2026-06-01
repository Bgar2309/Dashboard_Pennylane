"""Génère le TEXTE des brouillons de relance. Templates FR déterministes.
Ton adapté au niveau : FIRST douce, SECOND ferme, FORMAL mise en demeure.
Aucun LLM, aucun I/O, aucune DB.
"""
from datetime import date
from decimal import Decimal

from core.models import Customer, Invoice, ReminderLevel

# Libellés de colonnes du tableau des factures dues.
_HEADERS = ("Numéro", "Date", "Échéance", "Montant", "Reste dû")

# Objet du mail adapté au niveau de relance.
_OBJETS = {
    ReminderLevel.FIRST: "Rappel : facture(s) en attente de règlement",
    ReminderLevel.SECOND: "Relance : facture(s) échue(s) impayée(s)",
    ReminderLevel.FORMAL: "Mise en demeure de payer",
}

# Corps d'introduction, du ton le plus courtois au plus ferme.
_INTROS = {
    ReminderLevel.FIRST: (
        "Sauf erreur ou omission de notre part, nous constatons que la ou les "
        "facture(s) suivante(s) demeure(nt) à ce jour impayée(s). Il s'agit "
        "peut-être d'un simple oubli ; nous vous serions reconnaissants de bien "
        "vouloir procéder à leur règlement dès que possible."
    ),
    ReminderLevel.SECOND: (
        "Malgré notre précédent rappel, nous n'avons à ce jour pas reçu le "
        "règlement de la ou des facture(s) ci-dessous, désormais échue(s). "
        "Nous vous demandons de bien vouloir régulariser votre situation sans délai."
    ),
    ReminderLevel.FORMAL: (
        "Malgré nos relances successives, la ou les facture(s) suivante(s) "
        "restent impayées. Par la présente, et conformément aux articles L441-10 "
        "et suivants du Code de commerce, nous vous mettons en demeure de procéder "
        "au paiement de l'intégralité des sommes dues sous huitaine."
    ),
}

# Formule de clôture adaptée au niveau.
_CLOTURES = {
    ReminderLevel.FIRST: (
        "Si votre règlement a été effectué entre-temps, nous vous prions de ne "
        "pas tenir compte de ce message.\n\n"
        "Restant à votre disposition pour toute question, nous vous prions "
        "d'agréer, Madame, Monsieur, l'expression de nos salutations distinguées."
    ),
    ReminderLevel.SECOND: (
        "À défaut de règlement sous huitaine, nous nous verrons contraints "
        "d'engager une procédure de recouvrement.\n\n"
        "Dans l'attente de votre règlement, nous vous prions d'agréer, "
        "Madame, Monsieur, nos salutations distinguées."
    ),
    ReminderLevel.FORMAL: (
        "À défaut de paiement dans ce délai, nous nous réservons le droit "
        "d'engager toute action judiciaire de recouvrement, sans nouvel avis, "
        "des intérêts de retard et de l'indemnité forfaitaire de 40 € pour frais "
        "de recouvrement s'ajoutant au principal.\n\n"
        "Nous vous prions d'agréer, Madame, Monsieur, l'expression de nos "
        "salutations distinguées."
    ),
}


def _fmt_date(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d is not None else "—"


def _fmt_amount(amount: Decimal, currency: str) -> str:
    """Montant à la française : '1 234,56 €' (espace milliers, virgule décimale)."""
    sign = "-" if amount < 0 else ""
    entier, _, dec = f"{abs(amount):.2f}".partition(".")
    groupes = []
    while len(entier) > 3:
        groupes.insert(0, entier[-3:])
        entier = entier[:-3]
    groupes.insert(0, entier)
    symbole = "€" if currency.upper() in ("EUR", "€") else currency
    return f"{sign}{' '.join(groupes)},{dec} {symbole}"


def _render_table(invoices: list[Invoice]) -> str:
    """Tableau texte aligné (colonnes à largeur fixe) des factures dues."""
    rows = [
        (
            inv.number,
            _fmt_date(inv.date),
            _fmt_date(inv.due_date),
            _fmt_amount(inv.amount, inv.currency),
            _fmt_amount(inv.remaining_amount, inv.currency),
        )
        for inv in invoices
    ]

    widths = [
        max([len(_HEADERS[i])] + [len(r[i]) for r in rows])
        for i in range(len(_HEADERS))
    ]

    def line(cells: tuple[str, ...]) -> str:
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    sep = "-+-".join("-" * w for w in widths)
    out = [line(_HEADERS), sep]
    out.extend(line(r) for r in rows)
    return "\n".join(out)


class DraftGenerator:
    def render(self, customer: Customer, invoices: list[Invoice],
               level: ReminderLevel, today: date) -> str:
        """Texte prêt à copier-coller (corps + tableau des factures dues)."""
        if level not in _OBJETS:
            raise ValueError(
                f"Niveau de relance non géré pour un brouillon : {level}"
            )

        currency = invoices[0].currency if invoices else "EUR"
        total = sum((inv.remaining_amount for inv in invoices), Decimal("0"))

        parts = [
            f"Objet : {_OBJETS[level]}",
            "",
            "Madame, Monsieur,",
            "",
            _INTROS[level],
            "",
            _render_table(invoices),
            "",
            f"Total dû : {_fmt_amount(total, currency)}",
            "",
            _CLOTURES[level],
            "",
            customer.name,
            f"Le {_fmt_date(today)}",
        ]
        return "\n".join(parts)
