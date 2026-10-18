from odoo import api, fields, models
from odoo.exceptions import UserError


class EactaClassDeliberationWizard(models.TransientModel):
    _name = 'eacta.class.deliberation.wizard'
    _description = 'Assistant de PV de délibération'

    class_id = fields.Many2one('eacta.class', string='Classe', required=True)
    academic_year_id = fields.Many2one(
        'eacta.academic.year', string='Année académique', required=True,
        default=lambda self: self.env['eacta.academic.year'].get_current_year())
    period_type = fields.Selection([
        ('term', 'Trimestriel / Semestriel'),
        ('year', 'Bilan Annuel'),
    ], string='Période', default='term', required=True)
    term_id = fields.Many2one(
        'eacta.term', string='Trimestre',
        domain="[('academic_year_id', '=', academic_year_id)]")
    council_date = fields.Date(
        string='Date du conseil', default=fields.Date.context_today, required=True)
    president_name = fields.Char(string='Président du conseil (Direction)')
    secretary_name = fields.Char(string='Secrétaire / Professeur principal')
    general_notes = fields.Text(string='Observations générales du conseil')
    recompute_before_print = fields.Boolean(
        string='Recalculer les moyennes avant impression', default=True)

    @api.onchange('class_id')
    def _onchange_class_id(self):
        if self.class_id:
            if self.class_id.academic_year_id:
                self.academic_year_id = self.class_id.academic_year_id
            if self.class_id.teacher_id:
                self.secretary_name = self.class_id.teacher_id.name

    @api.onchange('academic_year_id')
    def _onchange_academic_year_id(self):
        if self.academic_year_id and self.academic_year_id.term_ids:
            self.term_id = self.academic_year_id.term_ids[:1]
        else:
            self.term_id = False

    def action_print_pv(self):
        """Lance l'impression du procès-verbal de délibération."""
        self.ensure_one()
        if self.period_type == 'term' and not self.term_id:
            raise UserError("Veuillez sélectionner un trimestre pour la délibération trimestrielle.")

        if self.recompute_before_print:
            term_arg = self.term_id if self.period_type == 'term' else None
            self.env['eacta.student.result'].compute_all_results(
                academic_year=self.academic_year_id,
                term=term_arg,
                classes=self.class_id
            )

        return self.env.ref('eacta_school.action_report_class_deliberation').report_action(self)

    def get_deliberation_data(self):
        """Retourne les données structurées des résultats des élèves pour le PV."""
        self.ensure_one()
        Result = self.env['eacta.student.result']
        domain = [
            ('class_id', '=', self.class_id.id),
            ('academic_year_id', '=', self.academic_year_id.id),
            ('result_type', '=', self.period_type),
        ]
        if self.period_type == 'term':
            domain.append(('term_id', '=', self.term_id.id))
        else:
            domain.append(('term_id', '=', False))

        results = Result.search(domain, order='average desc, rank asc')

        # Statistiques
        averages = [r.average for r in results]
        total_students = len(results)
        class_avg = round(sum(averages) / total_students, 2) if total_students else 0.0
        passed_count = len([a for a in averages if a >= 10.0])
        success_rate = round(100.0 * passed_count / total_students, 1) if total_students else 0.0
        max_avg = max(averages) if averages else 0.0
        min_avg = min(averages) if averages else 0.0

        # Répartition des mentions
        mentions_count = {
            'felicitations': len(results.filtered(lambda r: r.honor_mention == 'felicitations')),
            'tableau_honneur': len(results.filtered(lambda r: r.honor_mention in ('tableau_honneur', 'honneur'))),
            'encouragements': len(results.filtered(lambda r: r.honor_mention == 'encouragements')),
            'compliments': len(results.filtered(lambda r: r.honor_mention == 'compliments')),
            'avertissement': len(results.filtered(lambda r: r.honor_mention == 'avertissement')),
            'blame': len(results.filtered(lambda r: r.honor_mention == 'blame')),
        }

        return {
            'results': results,
            'total_students': total_students,
            'class_avg': class_avg,
            'passed_count': passed_count,
            'failed_count': total_students - passed_count,
            'success_rate': success_rate,
            'max_avg': max_avg,
            'min_avg': min_avg,
            'mentions_count': mentions_count,
        }
