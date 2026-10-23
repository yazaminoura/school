import werkzeug
from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, UserError, MissingError
from odoo.addons.portal.controllers.portal import CustomerPortal


class SchoolCustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'school_student_count' in counters:
            # Recherche stricte sans sudo() : les règles d'enregistrement délimitent l'accès
            values['school_student_count'] = request.env['eacta.student'].search_count([])
        return values

    def _get_student_or_forbidden(self, student_id):
        """
        Contrôle d'accès strict sans raccourci sudo() :
        Vérifie l'existence et applique les règles de sécurité ir.rule.
        Renvoie 404 si introuvable, 403 si l'accès est interdit.
        """
        Student = request.env['eacta.student']
        student = Student.browse(student_id)
        if not student.exists():
            raise werkzeug.exceptions.NotFound()
        try:
            student.check_access('read')
            # Forcer la lecture d'un champ pour déclencher ir.rule au niveau ORM
            _ = student.name
        except (AccessError, UserError):
            raise werkzeug.exceptions.Forbidden()
        return student

    # -------------------------------------------------------------------------
    # 1. LISTE DES ENFANTS / TABLEAU DE BORD SCOLAIRE
    # -------------------------------------------------------------------------
    @http.route(['/my/school', '/my/school/children'], type='http', auth='user', website=True)
    def portal_my_school(self, **kwargs):
        # Strictement sans sudo()
        students = request.env['eacta.student'].search([])
        values = self._prepare_portal_layout_values()
        values.update({
            'students': students,
            'page_name': 'school_dashboard',
        })
        return request.render('eacta_school.portal_my_school', values)

    # -------------------------------------------------------------------------
    # 2. VUE DÉTAILLÉE D'UN ÉLÈVE
    # -------------------------------------------------------------------------
    @http.route(['/my/school/student/<int:student_id>'], type='http', auth='user', website=True)
    def portal_student_detail(self, student_id, **kwargs):
        student = self._get_student_or_forbidden(student_id)
        
        # Données associées accessibles selon les règles ir.rule
        grades_count = request.env['eacta.course.grade'].search_count([
            ('student_id', '=', student.id),
            ('state', '=', 'published'),
        ])
        absences_count = request.env['eacta.attendance'].search_count([
            ('student_id', '=', student.id),
            ('attendance_type', '=', 'absent'),
        ])
        fees_unpaid = request.env['eacta.student.fee'].search([
            ('student_id', '=', student.id),
            ('state', 'in', ('unpaid', 'partial')),
            ('is_cancelled', '=', False),
        ])
        balance_due = sum(fees_unpaid.mapped('amount_due'))

        values = self._prepare_portal_layout_values()
        values.update({
            'student': student,
            'grades_count': grades_count,
            'absences_count': absences_count,
            'balance_due': balance_due,
            'page_name': 'student_detail',
        })
        return request.render('eacta_school.portal_student_detail', values)

    # -------------------------------------------------------------------------
    # 3. EMPLOI DU TEMPS
    # -------------------------------------------------------------------------
    @http.route(['/my/school/student/<int:student_id>/timetable'], type='http', auth='user', website=True)
    def portal_student_timetable(self, student_id, **kwargs):
        student = self._get_student_or_forbidden(student_id)
        slots = request.env['eacta.timetable.slot'].search([
            ('class_id', '=', student.current_class_id.id),
        ], order='day_of_week, time_start') if student.current_class_id else request.env['eacta.timetable.slot']

        values = self._prepare_portal_layout_values()
        values.update({
            'student': student,
            'slots': slots,
            'page_name': 'student_timetable',
        })
        return request.render('eacta_school.portal_student_timetable', values)

    # -------------------------------------------------------------------------
    # 4. ASSIDUITÉ (ABSENCES & RETARDS)
    # -------------------------------------------------------------------------
    @http.route(['/my/school/student/<int:student_id>/attendance'], type='http', auth='user', website=True)
    def portal_student_attendance(self, student_id, **kwargs):
        student = self._get_student_or_forbidden(student_id)
        attendances = request.env['eacta.attendance'].search([
            ('student_id', '=', student.id),
        ], order='date desc, id desc')

        values = self._prepare_portal_layout_values()
        values.update({
            'student': student,
            'attendances': attendances,
            'absent_count': len(attendances.filtered(lambda a: a.attendance_type == 'absent')),
            'late_count': len(attendances.filtered(lambda a: a.attendance_type == 'late')),
            'justified_count': len(attendances.filtered(lambda a: a.justified)),
            'page_name': 'student_attendance',
        })
        return request.render('eacta_school.portal_student_attendance', values)

    # -------------------------------------------------------------------------
    # 5. NOTES (PUBLIÉES UNIQUEMENT) & BULLETINS
    # -------------------------------------------------------------------------
    @http.route(['/my/school/student/<int:student_id>/grades'], type='http', auth='user', website=True)
    def portal_student_grades(self, student_id, **kwargs):
        student = self._get_student_or_forbidden(student_id)
        # Seules les notes dont l'état est "published" sont consultables
        grades = request.env['eacta.course.grade'].search([
            ('student_id', '=', student.id),
            ('state', '=', 'published'),
        ], order='id desc')

        results = request.env['eacta.student.result'].search([
            ('student_id', '=', student.id),
        ], order='academic_year_id desc, term_id')

        values = self._prepare_portal_layout_values()
        values.update({
            'student': student,
            'grades': grades,
            'results': results,
            'page_name': 'student_grades',
        })
        return request.render('eacta_school.portal_student_grades', values)

    # -------------------------------------------------------------------------
    # 6. TÉLÉCHARGEMENT DU BULLETIN SCOLAIRE PDF
    # -------------------------------------------------------------------------
    @http.route(['/my/school/student/<int:student_id>/bulletin/<int:result_id>'], type='http', auth='user', website=True)
    def portal_download_bulletin(self, student_id, result_id, **kwargs):
        student = self._get_student_or_forbidden(student_id)
        result = request.env['eacta.student.result'].browse(result_id)
        if not result.exists() or result.student_id.id != student.id:
            raise werkzeug.exceptions.NotFound()
        try:
            result.check_access('read')
            _ = result.student_id.name
        except (AccessError, UserError):
            raise werkzeug.exceptions.Forbidden()

        # Le bulletin officiel porte sur eacta.student.result (et non eacta.student)
        report_ref = 'eacta_school.action_report_student_result'
        if not request.env.ref(report_ref, raise_if_not_found=False):
            raise werkzeug.exceptions.NotFound()

        pdf_content, _content_type = request.env['ir.actions.report']._render_qweb_pdf(report_ref, result.ids)
        term_name = result.term_id.name or result.term_key or 'periode'
        clean_filename = f"Bulletin_{student.name}_{term_name}.pdf".replace(' ', '_')
        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf_content)),
            ('Content-Disposition', f'attachment; filename="{clean_filename}"'),
        ]
        return request.make_response(pdf_content, headers=pdfhttpheaders)

    # -------------------------------------------------------------------------
    # 7. FRAIS, SOLDE & FACTURATION
    # -------------------------------------------------------------------------
    @http.route(['/my/school/student/<int:student_id>/fees'], type='http', auth='user', website=True)
    def portal_student_fees(self, student_id, **kwargs):
        student = self._get_student_or_forbidden(student_id)
        fees = request.env['eacta.student.fee'].search([
            ('student_id', '=', student.id),
        ], order='due_date asc, id desc')

        total_invoiced = sum(fees.filtered(lambda f: not f.is_cancelled).mapped('amount_total'))
        total_paid = sum(fees.filtered(lambda f: not f.is_cancelled).mapped('amount_paid'))
        total_due = sum(fees.filtered(lambda f: not f.is_cancelled).mapped('amount_due'))

        values = self._prepare_portal_layout_values()
        values.update({
            'student': student,
            'fees': fees,
            'total_invoiced': total_invoiced,
            'total_paid': total_paid,
            'total_due': total_due,
            'currency': fees[:1].currency_id if fees else False,
            'page_name': 'student_fees',
        })
        return request.render('eacta_school.portal_student_fees', values)

    # -------------------------------------------------------------------------
    # 8. TÉLÉCHARGEMENT DE LA FACTURE CLIENT (account.move) PDF
    # -------------------------------------------------------------------------
    @http.route(['/my/school/student/<int:student_id>/fee/<int:fee_id>/invoice'], type='http', auth='user', website=True)
    def portal_download_invoice(self, student_id, fee_id, **kwargs):
        student = self._get_student_or_forbidden(student_id)
        fee = request.env['eacta.student.fee'].browse(fee_id)
        if not fee.exists() or fee.student_id.id != student.id:
            raise werkzeug.exceptions.NotFound()
        try:
            fee.check_access('read')
        except (AccessError, UserError):
            raise werkzeug.exceptions.Forbidden()

        if not fee.move_id:
            raise werkzeug.exceptions.NotFound()

        move = fee.move_id
        try:
            move.check_access('read')
            _ = move.name
        except (AccessError, UserError):
            raise werkzeug.exceptions.Forbidden()

        report_ref = 'account.account_invoices'
        if not request.env.ref(report_ref, raise_if_not_found=False):
            raise werkzeug.exceptions.NotFound()

        pdf_content, _content_type = request.env['ir.actions.report']._render_qweb_pdf(report_ref, move.ids)
        clean_filename = f"Facture_{move.name or move.id}.pdf".replace('/', '_').replace(' ', '_')
        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf_content)),
            ('Content-Disposition', f'attachment; filename="{clean_filename}"'),
        ]
        return request.make_response(pdf_content, headers=pdfhttpheaders)
