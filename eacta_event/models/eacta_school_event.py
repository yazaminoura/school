from odoo import models, fields

class EactaSchoolEvent(models.Model):
    _name = 'eacta.school.event'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Événement scolaire E-ACTA'

    name = fields.Char(string="Nom de l'événement", required=True)
    date = fields.Date(string="Date de l'événement")
    description = fields.Text(string="Description")
    organizer_id = fields.Many2one('res.users', string="Organisateur")
    participant_ids = fields.Many2many('eacta.student',
                                       relation='eacta_event_student_rel',
                                       column1='event_id',
                                       column2='student_id',
                                       string="Participants")
    image = fields.Image(string="Image de l'événement", max_width=1920, max_height=1920)
