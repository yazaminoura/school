from odoo import models, api


class StudentResultsReport(models.AbstractModel):
   _name = 'report.eacta_school.report_student_results'
   _description = 'Rapport des résultats des élèves'


   @api.model
   def _get_report_values(self, docids, data=None):
       docs = self.env['eacta.student'].browse(docids)
       return {
           'doc_ids': docids,
           'doc_model': 'eacta.student',
           'docs': docs,
           'get_average_grade': self._get_average_grade,
       }


   def _get_average_grade(self, student):
       grades = student.course_ids.mapped('grade')
       filtered_grades = [grade for grade in grades if isinstance(grade, (int, float))]
       return round(sum(filtered_grades) / len(filtered_grades), 2) if filtered_grades else 0


   @api.model
   def _get_report_values(self, docids, data=None):
       docs = self.env['eacta.student'].browse(docids)
       return {
           'doc_ids': docids,
           'doc_model': 'eacta.student',
           'docs': docs,
           'get_average_grade': self._get_average_grade,
       }
