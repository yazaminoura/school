from odoo import api, fields, models


class EactaStudent(models.Model):
    _inherit = 'eacta.student'

    event_ids = fields.Many2many(
        'eacta.school.event',
        relation='eacta_event_student_rel',
        column1='student_id',
        column2='event_id',
        string="Événements",
    )
    event_count = fields.Integer(string="Nombre d'événements", compute='_compute_event_count')

    @api.depends('event_ids')
    def _compute_event_count(self):
        for student in self:
            student.event_count = len(student.event_ids)

    def action_view_events(self):
        self.ensure_one()
        return {
            'name': f"Événements de {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.school.event',
            'view_mode': 'kanban,list,form',
            'domain': [('participant_ids', 'in', self.id)],
            'context': {'default_participant_ids': [self.id]},
        }
