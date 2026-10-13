from odoo import api, models


class ClassResultsReport(models.AbstractModel):
    _name = 'report.eacta_school.report_class_results'
    _description = 'Relevé des résultats de la classe'

    @api.model
    def _get_report_values(self, docids, data=None):
        classes = self.env['eacta.class'].browse(docids)
        results = {}
        for klass in classes:
            rows = []
            for student in klass.student_ids:
                card = student._get_report_card(year=klass.year)
                rows.append({'student': student, 'average': card['average'], 'appreciation': card['appreciation'],
                             'has_grades': bool(card['lines'])})
            ranked = sorted([r for r in rows if r['has_grades']], key=lambda r: r['average'], reverse=True)
            for rank, row in enumerate(ranked, start=1):
                row['rank'] = rank
            rows = ranked + [dict(r, rank=False) for r in rows if not r['has_grades']]
            results[klass.id] = rows
        return {
            'doc_ids': docids,
            'doc_model': 'eacta.class',
            'docs': classes,
            'results': results,
        }
