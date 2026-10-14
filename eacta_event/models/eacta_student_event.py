from odoo import api, fields, models


class EactaStudent(models.Model):
    _inherit = 'eacta.student'

    event_registration_ids = fields.One2many('eacta.school.event.registration', 'student_id',
                                             string="Inscriptions aux événements")
    event_count = fields.Integer(string="Nombre d'événements", compute='_compute_event_count')

    @api.depends('event_registration_ids.state')
    def _compute_event_count(self):
        for student in self:
            student.event_count = len(student.event_registration_ids.filtered(lambda r: r.state != 'cancelled'))

    def action_view_events(self):
        self.ensure_one()
        return {
            'name': f"Événements de {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.school.event.registration',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }

    def action_register_event(self):
        """Ouvre un dialogue pour inscrire cet élève à un événement à venir."""
        self.ensure_one()
        return {
            'name': f"Inscrire {self.name} à un événement",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.school.event.registration',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_student_id': self.id,
                'default_class_id': self.current_class_id.id if self.current_class_id else False,
            },
        }
