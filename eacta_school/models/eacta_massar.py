import base64
import io

import xlsxwriter

from odoo import api, fields, models
from odoo.exceptions import UserError


def _split_name(full_name):
    """« Prénom Nom » -> (nom, prénom) : le dernier mot est considéré comme le nom de famille."""
    parts = (full_name or '').split()
    if len(parts) < 2:
        return full_name or '', ''
    return parts[-1], ' '.join(parts[:-1])


class EactaStudentMassar(models.Model):
    _inherit = 'eacta.student'

    massar_code = fields.Char(string='Code Massar', copy=False, index=True, tracking=True,
                              help="Identifiant national de l'élève dans le système Massar (ex : J130000001).")

    _sql_constraints = [
        ('massar_code_unique', 'UNIQUE(massar_code)', "Ce code Massar est déjà attribué à un autre élève."),
    ]


class EactaMassarExportWizard(models.TransientModel):
    _name = 'eacta.massar.export.wizard'
    _description = 'Export Massar'

    export_type = fields.Selection([
        ('students', 'Liste des élèves'),
        ('grades', 'Notes par matière'),
    ], string='Export', default='grades', required=True)
    academic_year_id = fields.Many2one('eacta.academic.year', string='Année académique', required=True,
                                       default=lambda self: self.env['eacta.academic.year'].get_current_year())
    term_id = fields.Many2one('eacta.term', string='Trimestre', domain="[('academic_year_id', '=', academic_year_id)]")
    class_ids = fields.Many2many('eacta.class', string='Classes',
                                 domain="[('academic_year_id', '=', academic_year_id)]")
    course_ids = fields.Many2many('eacta.course', string='Matières',
                                  help="Laisser vide pour exporter toutes les matières des classes choisies.")
    missing_code_count = fields.Integer(string='Élèves sans code Massar', compute='_compute_missing_code_count')
    file_data = fields.Binary(string='Fichier', readonly=True, attachment=False)
    file_name = fields.Char(string='Nom du fichier', readonly=True)
    state = fields.Selection([('draft', 'Paramètres'), ('done', 'Terminé')], default='draft')

    @api.depends('class_ids', 'academic_year_id')
    def _compute_missing_code_count(self):
        for wizard in self:
            students = wizard._get_classes().student_ids
            wizard.missing_code_count = len(students.filtered(lambda s: not s.massar_code))

    def _get_classes(self):
        self.ensure_one()
        if self.class_ids:
            return self.class_ids
        return self.env['eacta.class'].search([('academic_year_id', '=', self.academic_year_id.id)])

    def _get_course_average(self, student, course):
        """Moyenne de la matière : bulletin officiel si calculé, sinon moyenne des notes saisies."""
        Result = self.env['eacta.student.result']
        domain = [('student_id', '=', student.id), ('academic_year_id', '=', self.academic_year_id.id)]
        domain += [('result_type', '=', 'term'), ('term_id', '=', self.term_id.id)] if self.term_id \
            else [('result_type', '=', 'year')]
        line = Result.search(domain, limit=1).line_ids.filtered(lambda l: l.course_id == course)[:1]
        if line:
            return line.average
        grades = student.course_grade_ids.filtered(
            lambda g: g.course_id == course and g.status == 'graded'
            and g.academic_year_id == self.academic_year_id
            and (not self.term_id or g.term_id == self.term_id))
        return round(sum(grades.mapped('grade')) / len(grades), 2) if grades else None

    def action_export(self):
        self.ensure_one()
        classes = self._get_classes()
        if not classes:
            raise UserError("Aucune classe pour cette année académique.")
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        head = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
        cell = workbook.add_format({'border': 1})
        number = workbook.add_format({'border': 1, 'num_format': '0.00'})
        missing = workbook.add_format({'border': 1, 'bg_color': '#FCE4D6'})
        used_names = set()

        for klass in classes.sorted('name'):
            students = klass.student_ids.filtered(lambda s: s.state in ('draft', 'enrolled')).sorted('name')
            if self.export_type == 'students':
                sheets = [(klass.name, None)]
            else:
                courses = (self.course_ids & klass.course_ids) if self.course_ids else klass.course_ids
                sheets = [(f"{klass.name} - {course.code or course.name}", course) for course in courses]
            for title, course in sheets:
                sheet_name = title[:31].replace('/', '-')
                suffix = 2
                while sheet_name in used_names:
                    sheet_name = f"{title[:28]}_{suffix}"
                    suffix += 1
                used_names.add(sheet_name)
                sheet = workbook.add_worksheet(sheet_name)
                if course:
                    headers = ['Code Massar', 'Nom', 'Prénom', 'Note']
                else:
                    headers = ['Code Massar', 'Nom', 'Prénom', 'Date de naissance', 'Genre', 'Classe', 'Matricule']
                for col, label in enumerate(headers):
                    sheet.write(0, col, label, head)
                sheet.set_column(0, 0, 16)
                sheet.set_column(1, 2, 22)
                sheet.set_column(3, len(headers) - 1, 14)
                for row, student in enumerate(students, start=1):
                    last_name, first_name = _split_name(student.name)
                    sheet.write(row, 0, student.massar_code or '', cell if student.massar_code else missing)
                    sheet.write(row, 1, last_name, cell)
                    sheet.write(row, 2, first_name, cell)
                    if course:
                        avg = self._get_course_average(student, course)
                        if avg is None:
                            sheet.write_blank(row, 3, None, cell)
                        else:
                            sheet.write_number(row, 3, avg, number)
                    else:
                        gender = {'male': 'M', 'female': 'F'}.get(student.gender, '')
                        sheet.write(row, 3, fields.Date.to_string(student.date_of_birth) or '', cell)
                        sheet.write(row, 4, gender, cell)
                        sheet.write(row, 5, klass.name, cell)
                        sheet.write(row, 6, student.code or '', cell)
        workbook.close()

        period = self.term_id.name if self.term_id else 'Annuel'
        kind = 'Eleves' if self.export_type == 'students' else f"Notes_{period}"
        self.write({
            'file_data': base64.b64encode(output.getvalue()),
            'file_name': f"Massar_{kind}_{self.academic_year_id.name}.xlsx".replace(' ', '_'),
            'state': 'done',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
