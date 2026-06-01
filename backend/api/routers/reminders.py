"""Router reminders.
GET  /api/reminders               vue relances (avec blocage banque)
GET  /api/reminders/{cid}/draft   texte brouillon (NE LOGUE RIEN)
POST /api/reminders/{cid}/confirm {level, invoice_numbers, note} -> log envoi
GET  /api/reminders/history       historique loggé
"""
# TODO
