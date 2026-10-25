import werkzeug
from odoo import fields, http, _
from odoo.http import request
from odoo.exceptions import AccessError, UserError
from odoo.addons.eacta_school.controllers.portal import SchoolCustomerPortal


class SchoolEventPortal(SchoolCustomerPortal):

    @http.route(['/my/school/student/<int:student_id>/events'], type='http', auth='user', website=True)
    def portal_my_school_student_events(self, student_id, **kwargs):
        student = self._get_student_or_forbidden(student_id)

        # Inscriptions de l'élève aux événements confirmés, en cours ou terminés
        Registration = request.env['eacta.school.event.registration']
        registrations = Registration.search([
            ('student_id', '=', student.id),
            ('event_id.state', 'in', ('confirmed', 'in_progress', 'done')),
        ], order='event_date desc, id desc')

        values = self._prepare_portal_layout_values()
        values.update({
            'student': student,
            'registrations': registrations,
            'page_name': 'student_events',
            'subpage_slug': 'events',
            'authorized_success': kwargs.get('authorized') == '1',
            'is_parent_user': request.env.user.partner_id in student.parent_ids,
        })
        return request.render('eacta_event.portal_student_events', values)

    @http.route(['/my/school/student/<int:student_id>/event/<int:reg_id>/authorize'], type='http', auth='user', methods=['GET', 'POST'], website=True)
    def portal_my_school_student_event_authorize(self, student_id, reg_id, **kwargs):
        student = self._get_student_or_forbidden(student_id)
        Registration = request.env['eacta.school.event.registration']
        reg = Registration.browse(reg_id)
        if not reg.exists() or reg.student_id != student:
            raise werkzeug.exceptions.NotFound()

        # Contrôle d'accès : seul un parent déclaré de l'élève peut signer l'autorisation
        partner = request.env.user.partner_id
        if partner not in student.parent_ids and not request.env.is_admin():
            raise werkzeug.exceptions.Forbidden()

        reg.sudo().action_authorize_online(partner)
        return request.redirect(f'/my/school/student/{student.id}/events?authorized=1')
