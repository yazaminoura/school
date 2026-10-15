from odoo import api, fields, models
from odoo.exceptions import UserError


class EactaPromotionWizard(models.TransientModel):
    _name = 'eacta.promotion.wizard'
    _description = "Passage en classe supérieure"

    from_class_id = fields.Many2one('eacta.class', string='Classe actuelle', required=True)
    academic_year_id = fields.Many2one('eacta.academic.year', related='from_class_id.academic_year_id', string='Année actuelle')
    next_academic_year_id = fields.Many2one('eacta.academic.year', string='Année académique suivante', compute='_compute_next_year', store=True, readonly=False)
    year = fields.Char(related='from_class_id.year', string='Année (texte)')
    next_year = fields.Char(string='Année suivante (texte)', compute='_compute_next_year', store=True, readonly=False)
    to_class_id = fields.Many2one('eacta.class', string='Classe supérieure (admis)',
                                  domain="['|', ('academic_year_id', '=', next_academic_year_id), ('year', '=', next_year)]")
    repeat_class_id = fields.Many2one('eacta.class', string='Classe de redoublement',
                                      domain="['|', ('academic_year_id', '=', next_academic_year_id), ('year', '=', next_year)]")
    pass_mark = fields.Float(string="Moyenne d'admission", default=lambda self: float(self.env['ir.config_parameter'].sudo().get_param('eacta_school.pass_mark', 10.0)))
    line_ids = fields.One2many('eacta.promotion.wizard.line', 'wizard_id', string='Élèves')

    @api.depends('from_class_id', 'academic_year_id')
    def _compute_next_year(self):
        for wizard in self:
            curr_y = wizard.academic_year_id
            if curr_y:
                # Find the next academic year starting after current year's date_end
                nxt = self.env['eacta.academic.year'].search([('date_start', '>=', curr_y.date_end)], order='date_start asc', limit=1)
                wizard.next_academic_year_id = nxt or False
                wizard.next_year = nxt.name if nxt else (str(int(wizard.year) + 1) if wizard.year and wizard.year.isdigit() else wizard.year)
            else:
                year = wizard.from_class_id.year
                wizard.next_academic_year_id = False
                wizard.next_year = str(int(year) + 1) if year and year.isdigit() else year

    def _prepare_student_lines(self, from_class, pass_mark=10.0):
        if not from_class:
            return []
        lines = []
        Student = self.env['eacta.student']
        Result = self.env['eacta.student.result']
        curr_year = from_class.academic_year_id

        for student in from_class.student_ids.filtered(lambda s: s.state in ('draft', 'enrolled')).sorted('name'):
            # Rechercher d'abord le résultat annuel officiel
            avg = None
            if curr_year:
                res = Result.search([
                    ('student_id', '=', student.id),
                    ('academic_year_id', '=', curr_year.id),
                    ('result_type', '=', 'year'),
                ], limit=1)
                if res:
                    avg = res.average

            if avg is None:
                # Fallback : calcul direct des notes de la classe
                avg = Student._get_weighted_average(
                    student.course_grade_ids.filtered(lambda g: g.class_id == from_class)
                )

            decision = 'promote' if avg is None or avg >= pass_mark else 'repeat'
            lines.append((0, 0, {
                'student_id': student.id,
                'average': avg or 0.0,
                'has_grades': avg is not None,
                'decision': decision,
                'unpaid_balance': student.fee_balance,
            }))
        return lines

    @api.onchange('from_class_id', 'pass_mark')
    def _onchange_from_class(self):
        if not self.from_class_id:
            self.line_ids = [(5, 0, 0)]
            return
        self._compute_next_year()
        self.line_ids = [(5, 0, 0)] + self._prepare_student_lines(self.from_class_id, self.pass_mark)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        class_id = res.get('from_class_id') or self.env.context.get('default_from_class_id')
        if not class_id and self.env.context.get('active_model') == 'eacta.class':
            class_id = self.env.context.get('active_id')
        if class_id:
            res['from_class_id'] = class_id
            from_class = self.env['eacta.class'].browse(class_id)
            ICP = self.env['ir.config_parameter'].sudo()
            pass_mark = float(ICP.get_param('eacta_school.pass_mark', 10.0))
            res['pass_mark'] = pass_mark
            res['line_ids'] = self._prepare_student_lines(from_class, pass_mark)
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

        # Traitement des admis
        if promoted:
            self.to_class_id.student_ids = [(4, s.id) for s in promoted]
            promoted.filtered(lambda s: s.state == 'draft').write({'state': 'enrolled'})
            for s in promoted:
                if hasattr(s, '_sync_class_courses'):
                    s._sync_class_courses()

        # Traitement des redoublants
        if repeating:
            self.repeat_class_id.student_ids = [(4, s.id) for s in repeating]
            for s in repeating:
                if hasattr(s, '_sync_class_courses'):
                    s._sync_class_courses()

        # Traitement des diplômés et départs
        graduating.filtered(lambda s: s.state == 'enrolled').write({'state': 'graduated'})
        leaving.write({'state': 'alumni'})

        # Report des soldes impayés dans le chatter de chaque élève concerné
        with_balance = self.line_ids.filtered(lambda l: l.unpaid_balance > 0)
        for line in with_balance:
            line.student_id.message_post(
                body=(
                    f"<p><strong>Report de fin d'année :</strong> L'élève a un solde impayé de "
                    f"<strong>{line.unpaid_balance:.2f} {line.student_id.fee_currency_id.symbol or ''}</strong> "
                    f"reporté pour l'année scolaire suivante.</p>"
                ),
                message_type='notification'
            )

        self.from_class_id.message_post(body=(
            f"Passage de fin d'année : {len(promoted)} admis, {len(repeating)} redoublant(s), "
            f"{len(graduating)} diplômé(s), {len(leaving)} départ(s). "
            f"{len(with_balance)} élève(s) avec solde impayé reporté."))

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
    unpaid_balance = fields.Monetary(string='Solde impayé', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
