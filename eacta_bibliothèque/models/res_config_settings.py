from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    library_fine_per_day = fields.Float(
        string="Amende par jour de retard", config_parameter='library.fine_per_day', default=1.0)
    library_max_loans_student = fields.Integer(
        string="Emprunts simultanés (élève)", config_parameter='library.max_loans_student', default=3)
    library_max_loans_teacher = fields.Integer(
        string="Emprunts simultanés (enseignant)", config_parameter='library.max_loans_teacher', default=10)
    library_max_renewals = fields.Integer(
        string="Prolongations maximum", config_parameter='library.max_renewals', default=2)
