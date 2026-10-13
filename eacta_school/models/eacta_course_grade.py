# eacta_course_grade.py - FIXED VERSION
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date


class CourseGrade(models.Model):
    _name = 'eacta.course.grade'
    _description = 'Notes des Cours'

    course_id = fields.Many2one('eacta.course', string='Cours', required=True, ondelete='cascade')
    student_id = fields.Many2one('eacta.student', string='Étudiant', required=True, ondelete='cascade')
    grade = fields.Float(string="Note", required=True, digits=(3, 2))
    exam_id = fields.Many2one('eacta.exam', string="Examen", required=True)
    class_id = fields.Many2one('eacta.class', string='Classe', required=True)  # Added required=True


    @api.constrains('grade')
    def _check_grade_range(self):
        for record in self:
            if not (0.0 <= record.grade <= 20.0):
                raise ValidationError("La note doit être comprise entre 0 et 20.")

    @api.onchange('exam_id')
    def _onchange_exam_id(self):
        if self.exam_id:
            self.course_id = self.exam_id.course_id.id

    @api.constrains('exam_id', 'course_id')
    def _check_exam_course_consistency(self):
        for record in self:
            if record.exam_id and record.course_id:
                if record.exam_id.course_id != record.course_id:
                    raise ValidationError(
                        f"L'examen '{record.exam_id.name}' ne correspond pas au cours '{record.course_id.name}'. "
                        f"Cet examen appartient au cours '{record.exam_id.course_id.name}'."
                    )

    # In eacta_course_grade.py - ensure this method exists
    @api.onchange('student_id', 'exam_id')
    def _onchange_student_exam(self):
        if self.student_id and self.exam_id:
            # Find the class where this student is enrolled for the exam's year
            exam_year = self.exam_id.date.year if self.exam_id.date else False
            if exam_year:
                student_class = self.student_id.class_ids.filtered(
                    lambda c: c.year == str(exam_year)
                )
                if student_class:
                    self.class_id = student_class[0]
    @api.model
    def create(self, vals):
        if vals.get('exam_id') and not vals.get('course_id'):
            exam = self.env['eacta.exam'].browse(vals['exam_id'])
            vals['course_id'] = exam.course_id.id

        # Auto-set class_id if not provided
        if not vals.get('class_id') and vals.get('student_id'):
            student = self.env['eacta.student'].browse(vals['student_id'])
            if vals.get('exam_id'):
                exam = self.env['eacta.exam'].browse(vals['exam_id'])
                if exam.date:
                    exam_year = str(exam.date.year)
                    student_class = student.class_ids.filtered(lambda c: c.year == exam_year)
                    if student_class:
                        vals['class_id'] = student_class[0].id
            else:
                # If no exam, use current year class
                current_year = str(fields.Date.today().year)
                student_class = student.class_ids.filtered(lambda c: c.year == current_year)
                if student_class:
                    vals['class_id'] = student_class[0].id

        return super().create(vals)

    def write(self, vals):
        if vals.get('exam_id') and not vals.get('course_id'):
            exam = self.env['eacta.exam'].browse(vals['exam_id'])
            vals['course_id'] = exam.course_id.id
        return super().write(vals)

    @api.constrains('exam_id')
    def _check_exam_date_in_past(self):
        for record in self:
            if record.exam_id and record.exam_id.date:
                if record.exam_id.date > date.today():
                    raise ValidationError("La date de l'examen doit être déjà passée.")

    @api.onchange('student_id')
    def _onchange_student_id_class(self):
        if self.student_id:
            return {'domain': {'class_id': [('id', 'in', self.student_id.class_ids.ids)]}}
        return {'domain': {'class_id': []}}

    @api.constrains('student_id', 'class_id')
    def _check_class_belongs_to_student(self):
        for record in self:
            if record.class_id and record.class_id not in record.student_id.class_ids:
                raise ValidationError("La classe sélectionnée ne correspond pas aux classes de l'étudiant.")