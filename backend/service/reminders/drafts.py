"""Génère le TEXTE des brouillons de relance. Templates FR déterministes.
Ton adapté au niveau : FIRST douce, SECOND ferme, FORMAL mise en demeure.
Aucun LLM, aucun I/O, aucune DB.
"""
from datetime import date

from core.models import Customer, Invoice, ReminderLevel


class DraftGenerator:
    def render(self, customer: Customer, invoices: list[Invoice],
               level: ReminderLevel, today: date) -> str:
        """Texte prêt à copier-coller (corps + tableau des factures dues)."""
        raise NotImplementedError
