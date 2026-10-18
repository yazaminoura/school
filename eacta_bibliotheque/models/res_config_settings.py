from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    library_enable_overdue_fines = fields.Boolean(
        string="Activer les amendes de retard", config_parameter='library.enable_overdue_fines', default=False,
        help="Appliquer une pénalité financière pour chaque jour de retard lors du retour des livres."
    )
    library_fine_per_day = fields.Float(
        string="Amende par jour de retard", config_parameter='library.fine_per_day', default=1.0)
    library_send_overdue_reminder_email = fields.Boolean(
        string="Envoyer des rappels par email en cas de retard", config_parameter='library.send_overdue_reminder_email',
        default=True, help="Notifier automatiquement l'emprunteur ou ses parents en cas d'emprunt en retard."
    )
    library_overdue_reminder_interval_days = fields.Integer(
        string="Intervalle minimum entre relances (jours)", config_parameter='library.overdue_reminder_interval_days',
        default=7, help="Nombre de jours minimum à attendre avant de réémettre une relance pour le même emprunt."
    )
    library_max_loans_student = fields.Integer(
        string="Emprunts simultanés (élève)", config_parameter='library.max_loans_student', default=3)
    library_max_loans_teacher = fields.Integer(
        string="Emprunts simultanés (enseignant)", config_parameter='library.max_loans_teacher', default=10)
    library_max_renewals = fields.Integer(
        string="Prolongations maximum", config_parameter='library.max_renewals', default=2)
