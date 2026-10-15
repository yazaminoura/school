from odoo import api, fields, models
from odoo.exceptions import UserError

from .eacta_course_grade import APPRECIATIONS, appreciation_for

HONOR_MENTIONS = [
    ('felicitations', 'Félicitations'),
    ('compliments', 'Compliments'),
    ('encouragements', 'Encouragements'),
    ('honneur', "Table d'honneur"),
    ('avertissement', 'Avertissement de travail'),
    ('blame', 'Blâme'),
]


def honor_mention_for(avg):
    if avg is None:
        return False
    if avg >= 16.0:
        return 'felicitations'
    if avg >= 14.0:
        return 'compliments'
    if avg >= 12.0:
        return 'encouragements'
    if avg >= 10.0:
        return 'honneur'
    return False


class EactaStudentResult(models.Model):
    _name = 'eacta.student.result'
    _description = 'Résultat scolaire'
    _order = 'academic_year_id desc, term_id, average desc'
    _rec_name = 'display_name'

    student_id = fields.Many2one('eacta.student', string='Élève', required=True, ondelete='cascade', index=True)
    academic_year_id = fields.Many2one('eacta.academic.year', string='Année académique', required=True, ondelete='cascade', index=True)
    class_id = fields.Many2one('eacta.class', string='Classe', index=True)
    term_id = fields.Many2one('eacta.term', string='Trimestre', ondelete='cascade', index=True)
    term_key = fields.Integer(string='Clé Trimestre', compute='_compute_term_key', store=True, index=True)
    result_type = fields.Selection([
        ('term', 'Trimestriel'),
        ('year', 'Annuel'),
    ], string='Type de bilan', default='term', required=True, index=True)
    average = fields.Float(string='Moyenne générale', digits=(4, 2), aggregator='avg')
    rank = fields.Integer(string='Rang')
    class_size = fields.Integer(string='Effectif')
    class_average = fields.Float(string='Moyenne de la classe', digits=(4, 2))
    appreciation = fields.Selection(APPRECIATIONS, string='Appréciation', compute='_compute_appreciation', store=True)
    honor_mention = fields.Selection(HONOR_MENTIONS, string='Mention du conseil', compute='_compute_appreciation', store=True)
    passed = fields.Boolean(string='Admis / Validé', compute='_compute_appreciation', store=True)

    line_ids = fields.One2many('eacta.student.result.line', 'result_id', string='Notes par matière')
    absence_count = fields.Integer(string='Absences')
    unjustified_absence_count = fields.Integer(string='Absences non justifiées')
    late_count = fields.Integer(string='Retards')
    teacher_remarks = fields.Text(string='Appréciation globale du conseil')

    _sql_constraints = [
        ('student_period_unique', 'UNIQUE(student_id, academic_year_id, result_type, term_key)',
         "Un bulletin / bilan existe déjà pour cet élève sur cette période !")
    ]

    @api.depends('term_id')
    def _compute_term_key(self):
        for rec in self:
            rec.term_key = rec.term_id.id if rec.term_id else 0

    @api.depends('average')
    def _compute_appreciation(self):
        ICP = self.env['ir.config_parameter'].sudo()
        pass_mark = float(ICP.get_param('eacta_school.pass_mark', 10.0))
        for rec in self:
            rec.appreciation = appreciation_for(rec.average)
            rec.honor_mention = honor_mention_for(rec.average)
            rec.passed = rec.average >= pass_mark

    @api.depends('student_id.name', 'academic_year_id.name', 'term_id.name', 'result_type')
    def _compute_display_name(self):
        for rec in self:
            period = rec.term_id.name if rec.result_type == 'term' and rec.term_id else "Bilan Annuel"
            y_name = rec.academic_year_id.name or ''
            s_name = rec.student_id.name or ''
            rec.display_name = f"{s_name} - {period} ({y_name})"

    def action_print_bulletin(self):
        self.ensure_one()
        return self.env.ref('eacta_school.action_report_student_result').report_action(self)

    @api.model
    def compute_all_results(self, academic_year=None, term=None, classes=None):
        """Calcul efficace des moyennes pondérées par matière, trimestrielles et annuelles."""
        ICP = self.env['ir.config_parameter'].sudo()
        weights = {
            'quiz': float(ICP.get_param('eacta_school.weight_quiz', 1.0)),
            'homework': float(ICP.get_param('eacta_school.weight_homework', 1.0)),
            'oral': float(ICP.get_param('eacta_school.weight_oral', 1.0)),
            'practical': float(ICP.get_param('eacta_school.weight_practical', 1.0)),
            'midterm': float(ICP.get_param('eacta_school.weight_midterm', 2.0)),
            'final': float(ICP.get_param('eacta_school.weight_final', 3.0)),
        }
        absent_policy = ICP.get_param('eacta_school.absent_policy', 'excluded')
        unjustified_zero = ICP.get_param('eacta_school.unjustified_absence_zero', 'True') in ('True', '1', True)
        pass_mark = float(ICP.get_param('eacta_school.pass_mark', 10.0))

        if not academic_year:
            academic_year = self.env['eacta.academic.year'].get_current_year()
        if not academic_year:
            return

        target_classes = classes or self.env['eacta.class'].search([('academic_year_id', '=', academic_year.id)])
        if not target_classes:
            return

        all_students = target_classes.student_ids
        if not all_students:
            return

        terms = [term] if term else academic_year.term_ids

        # 1. Récupérer toutes les notes de l'année pour ces élèves
        grade_domain = [
            ('academic_year_id', '=', academic_year.id),
            ('student_id', 'in', all_students.ids),
        ]
        all_grades = self.env['eacta.course.grade'].search(grade_domain)

        # Regrouper les notes: grades_by_student_term_course[student_id][term_id][course_id] = list of (grade, weight)
        data = {}
        for g in all_grades:
            t_id = g.term_id.id if g.term_id else 0
            s_id = g.student_id.id
            c_id = g.course_id.id
            if not c_id:
                continue

            num_grade = None
            w = weights.get(g.exam_type, 1.0)
            if g.status == 'graded':
                num_grade = g.grade
            elif g.status == 'absent':
                if absent_policy == 'zero' or (unjustified_zero and not g.is_justified):
                    num_grade = 0.0
                else:
                    continue  # Excluded
            else:
                continue  # Pending or exempt

            if num_grade is not None:
                data.setdefault(s_id, {}).setdefault(t_id, {}).setdefault(c_id, []).append((num_grade, w))

        # 2. Récupérer les assiduités en 1 requête
        att_domain = [
            ('student_id', 'in', all_students.ids),
            ('date', '>=', academic_year.date_start),
            ('date', '<=', academic_year.date_end),
        ]
        attendances = self.env['eacta.attendance'].search(att_domain)
        # att_stats[student_id][term_id] = {'total_abs': 0, 'unjust_abs': 0, 'late': 0}
        att_stats = {}
        for att in attendances:
            s_id = att.student_id.id
            # Déterminer le trimestre de l'assiduité
            t_id = 0
            for t in academic_year.term_ids:
                if t.date_start <= att.date <= t.date_end:
                    t_id = t.id
                    break
            for period_key in (t_id, 'year'):
                bucket = att_stats.setdefault(s_id, {}).setdefault(period_key, {'total_abs': 0, 'unjust_abs': 0, 'late': 0})
                if att.attendance_type == 'absent':
                    bucket['total_abs'] += 1
                    if not att.justified:
                        bucket['unjust_abs'] += 1
                elif att.attendance_type == 'late':
                    bucket['late'] += 1

        # 3. Calcul par classe et par trimestre
        courses_by_id = {c.id: c for c in self.env['eacta.course'].search([])}
        student_results_to_upsert = []

        for klass in target_classes:
            k_students = klass.student_ids
            if not k_students:
                continue

            for t in terms:
                t_id = t.id
                term_student_averages = []
                student_lines = {}

                for student in k_students:
                    s_id = student.id
                    course_evals = data.get(s_id, {}).get(t_id, {})
                    lines_data = []
                    weighted_sum = 0.0
                    total_coef = 0.0

                    for c_id, evals in course_evals.items():
                        course = courses_by_id.get(c_id)
                        if not course or not evals:
                            continue
                        sum_gw = sum(g * w for g, w in evals)
                        sum_w = sum(w for g, w in evals)
                        subject_avg = round(sum_gw / sum_w, 2) if sum_w else 0.0
                        coef = course.coefficient or 1.0

                        weighted_sum += subject_avg * coef
                        total_coef += coef

                        lines_data.append({
                            'course_id': c_id,
                            'coefficient': coef,
                            'average': subject_avg,
                            'appreciation': appreciation_for(subject_avg),
                            'passed': subject_avg >= pass_mark,
                            'teacher_id': course.teacher_id.id if course.teacher_id else False,
                        })

                    if total_coef > 0:
                        term_avg = round(weighted_sum / total_coef, 2)
                        term_student_averages.append((s_id, term_avg, lines_data))
                    else:
                        term_student_averages.append((s_id, 0.0, lines_data))

                # Calcul des rangs avec égalités (dense ranking)
                sorted_term = sorted(term_student_averages, key=lambda x: x[1], reverse=True)
                cls_size = len(sorted_term)
                cls_avg = round(sum(x[1] for x in sorted_term) / cls_size, 2) if cls_size else 0.0

                ranks = {}
                current_rank = 1
                for idx, (s_id, avg, _) in enumerate(sorted_term):
                    if idx > 0 and avg < sorted_term[idx - 1][1]:
                        current_rank = idx + 1
                    ranks[s_id] = current_rank

                for s_id, avg, l_data in sorted_term:
                    att_info = att_stats.get(s_id, {}).get(t_id, {})
                    student_results_to_upsert.append({
                        'student_id': s_id,
                        'academic_year_id': academic_year.id,
                        'class_id': klass.id,
                        'term_id': t_id,
                        'result_type': 'term',
                        'average': avg,
                        'rank': ranks.get(s_id, 1),
                        'class_size': cls_size,
                        'class_average': cls_avg,
                        'absence_count': att_info.get('total_abs', 0),
                        'unjustified_absence_count': att_info.get('unjust_abs', 0),
                        'late_count': att_info.get('late', 0),
                        'lines': l_data,
                    })

            # 4. Calcul annuel pour la classe
            year_student_averages = []
            for student in k_students:
                s_id = student.id
                term_avgs = []
                total_term_weight = 0.0
                weighted_term_sum = 0.0

                for t in academic_year.term_ids:
                    # Trouver la moyenne du trimestre t
                    for item in student_results_to_upsert:
                        if item['student_id'] == s_id and item['term_id'] == t.id and item['result_type'] == 'term':
                            w_t = t.weight or 1.0
                            weighted_term_sum += item['average'] * w_t
                            total_term_weight += w_t
                            break

                year_avg = round(weighted_term_sum / total_term_weight, 2) if total_term_weight else 0.0
                year_student_averages.append((s_id, year_avg))

            sorted_year = sorted(year_student_averages, key=lambda x: x[1], reverse=True)
            cls_size = len(sorted_year)
            cls_avg = round(sum(x[1] for x in sorted_year) / cls_size, 2) if cls_size else 0.0

            year_ranks = {}
            current_rank = 1
            for idx, (s_id, avg) in enumerate(sorted_year):
                if idx > 0 and avg < sorted_year[idx - 1][1]:
                    current_rank = idx + 1
                year_ranks[s_id] = current_rank

            for s_id, avg in sorted_year:
                att_info = att_stats.get(s_id, {}).get('year', {})
                student_results_to_upsert.append({
                    'student_id': s_id,
                    'academic_year_id': academic_year.id,
                    'class_id': klass.id,
                    'term_id': False,
                    'result_type': 'year',
                    'average': avg,
                    'rank': year_ranks.get(s_id, 1),
                    'class_size': cls_size,
                    'class_average': cls_avg,
                    'absence_count': att_info.get('total_abs', 0),
                    'unjustified_absence_count': att_info.get('unjust_abs', 0),
                    'late_count': att_info.get('late', 0),
                    'lines': [],
                })

        # 5. Enregistrer les résultats (création ou mise à jour)
        for res_dict in student_results_to_upsert:
            lines = res_dict.pop('lines', [])
            domain = [
                ('student_id', '=', res_dict['student_id']),
                ('academic_year_id', '=', res_dict['academic_year_id']),
                ('result_type', '=', res_dict['result_type']),
                ('term_id', '=', res_dict['term_id']),
            ]
            existing = self.search(domain, limit=1)
            if existing:
                existing.write(res_dict)
                rec = existing
            else:
                rec = self.create(res_dict)

            if lines:
                # Mettre à jour les lignes de matières
                rec.line_ids.unlink()
                line_vals = [dict(l, result_id=rec.id) for l in lines]
                self.env['eacta.student.result.line'].create(line_vals)

        # 6. Mettre à jour la moyenne annuelle sur la fiche élève (student.average)
        for student in all_students:
            yr_res = self.search([
                ('student_id', '=', student.id),
                ('academic_year_id', '=', academic_year.id),
                ('result_type', '=', 'year'),
            ], limit=1)
            if yr_res:
                student.average = yr_res.average
                student.class_rank = yr_res.rank
                student.class_size = yr_res.class_size


class EactaStudentResultLine(models.Model):
    _name = 'eacta.student.result.line'
    _description = 'Ligne de résultat par matière'
    _order = 'result_id, course_id'

    result_id = fields.Many2one('eacta.student.result', string='Bulletin', required=True, ondelete='cascade', index=True)
    course_id = fields.Many2one('eacta.course', string='Matière', required=True, index=True)
    coefficient = fields.Float(string='Coeff.', default=1.0)
    average = fields.Float(string='Moyenne', digits=(4, 2))
    appreciation = fields.Selection(APPRECIATIONS, string='Appréciation')
    passed = fields.Boolean(string='Validé')
    teacher_id = fields.Many2one('res.users', string='Enseignant')
    teacher_remarks = fields.Char(string='Observation')
