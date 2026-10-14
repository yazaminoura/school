from odoo import api, fields, models
from odoo.exceptions import UserError


class EactaPromotionWizard(models.TransientModel):
    _name = 'eacta.promotion.wizard'
    _description = "Passage en classe supérieure"

    from_class_id = fields.Many2one('eacta.class', string='Classe actuelle', required=True)
    year = fields.Char(related='from_class_id.year', string='Année')
    next_year = fields.Char(string='Année suivante', compute='_compute_next_year', store=True, readonly=False)
    to_class_id = fields.Many2one('eacta.class', string='Classe supérieure (admis)',
                                  domain="[('year', '=', next_year)]")
    repeat_class_id = fields.Many2one('eacta.class', string='Classe de redoublement',
                                      domain="[('year', '=', next_year)]")
    pass_mark = fields.Float(string="Moyenne d'admission", default=10.0)
    line_ids = fields.One2many('eacta.promotion.wizard.line', 'wizard_id', string='Élèves')

    @api.depends('from_class_id')
    def _compute_next_year(self):
        for wizard in self:
            year = wizard.from_class_id.year
            wizard.next_year = str(int(year) + 1) if year and year.isdigit() else year

    @api.onchange('from_class_id', 'pass_mark')
    def _onchange_from_class(self):
        lines = [(5, 0, 0)]
        for student in self.from_class_id.student_ids.filtered(lambda s: s.state in ('draft', 'enrolled')):
            average = self.env['eacta.student']._get_weighted_average(
                student.course_grade_ids.filtered(lambda g: g.class_id == self.from_class_id))
            decision = 'promote' if average is None or average >= self.pass_mark else 'repeat'
            lines.append((0, 0, {'student_id': student.id, 'average': average or 0.0,
                                 'has_grades': average is not None, 'decision': decision}))
        self.line_ids = lines

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'eacta.class' and self.env.context.get('active_id'):
            res['from_class_id'] = self.env.context['active_id']
        return res

    def action_apply(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError("Aucun élève à traiter.")
        promoted = self.line_ids.filtered(lambda l: l.decision == 'promote').student_id
        repeating = self.line_ids.filtered(lambda l: l.decision == 'repeat').student_id
        graduating = self.line_ids.filtered(lambda l: l.decision == 'graduate').student_id
        leaving = self.line_ids.filtered(lambda l: l.decision == 'leave').student_id
        if promoted and not self.to_class_id:
            raise UserError("Choisissez la classe supérieure pour les élèves admis.")
        if repeating and not self.repeat_class_id:
            raise UserError("Choisissez la classe de redoublement pour les élèves non admis.")
        if promoted:
            self.to_class_id.student_ids = [(4, s.id) for s in promoted]
        if repeating:
            self.repeat_class_id.student_ids = [(4, s.id) for s in repeating]
        graduating.filtered(lambda s: s.state == 'enrolled').write({'state': 'graduated'})
        leaving.write({'state': 'alumni'})
        self.from_class_id.message_post(body=(
            f"Passage de fin d'année : {len(promoted)} admis, {len(repeating)} redoublant(s), "
            f"{len(graduating)} diplômé(s), {len(leaving)} départ(s)."))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Passage de fin d'année effectué",
                'message': f"{len(promoted)} admis · {len(repeating)} redoublant(s) · "
                           f"{len(graduating)} diplômé(s) · {len(leaving)} départ(s)",
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class EactaPromotionWizardLine(models.TransientModel):
    _name = 'eacta.promotion.wizard.line'
    _description = "Décision de passage"
    _order = 'average desc'

    wizard_id = fields.Many2one('eacta.promotion.wizard', required=True, ondelete='cascade')
    student_id = fields.Many2one('eacta.student', string='Élève', required=True)
    average = fields.Float(string='Moyenne', digits=(4, 2))
    has_grades = fields.Boolean(string='Notes')
    decision = fields.Selection([
        ('promote', 'Admis'),
        ('repeat', 'Redouble'),
        ('graduate', 'Diplômé'),
        ('leave', 'Quitte l\'école'),
    ], string='Décision', required=True, default='promote')
