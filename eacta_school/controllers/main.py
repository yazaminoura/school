import logging
import werkzeug
from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class SchoolMainController(http.Controller):

    # -------------------------------------------------------------------------
    # 1. EXPORT DE L'EMPLOI DU TEMPS AU FORMAT iCALENDAR (.ics)
    # -------------------------------------------------------------------------
    @http.route('/school/timetable/ics/<string:mode>/<int:record_id>', type='http', auth='user', website=False)
    def export_timetable_ics(self, mode, record_id, **kwargs):
        """
        Téléchargement du fichier iCalendar (.ics) pour une classe ou un enseignant.
        Contrôle d'accès strict sans raccourci sudo().
        """
        if mode not in ('class', 'teacher'):
            raise werkzeug.exceptions.NotFound()

        try:
            ics_content = request.env['eacta.timetable.slot'].export_ics(mode, record_id)
        except AccessError:
            raise werkzeug.exceptions.Forbidden()

        if not ics_content:
            raise werkzeug.exceptions.NotFound()

        filename = f"Emploi_du_temps_{mode}_{record_id}.ics"
        headers = [
            ('Content-Type', 'text/calendar; charset=utf-8'),
            ('Content-Length', len(ics_content.encode('utf-8'))),
            ('Content-Disposition', f'attachment; filename="{filename}"'),
        ]
        return request.make_response(ics_content, headers=headers)

    # -------------------------------------------------------------------------
    # 2. VUE DE SCAN ET ENREGISTREMENT D'ASSIDUITÉ 1-CLIC (MOBILE)
    # -------------------------------------------------------------------------
    @http.route(['/school/attendance/scan'], type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=False)
    def attendance_scan_view(self, token=None, **kwargs):
        """
        Interface mobile d'enregistrement d'assiduité par scan de QR code d'élève.
        Le QR code porte un jeton cryptographique signé et non devinable (qr_token).
        Accessible au personnel scolaire autorisé (enseignants, surveillants, secrétariat, manager).
        """
        user = request.env.user
        # Vérification des droits : l'utilisateur doit faire partie du personnel scolaire
        has_school_rights = user.has_group('eacta_school.group_eacta_school_user') or user.has_group('base.group_system')
        if not has_school_rights:
            raise werkzeug.exceptions.Forbidden("Accès réservé au personnel scolaire autorisé.")

        student_data = None
        attendance_created = None
        error_message = None

        if token:
            token = token.strip()
            # Recherche stricte sans sudo : application des droits d'accès
            student = request.env['eacta.student'].search([('qr_token', '=', token)], limit=1)
            if not student:
                error_message = "Jeton QR code invalide ou élève introuvable."
            else:
                # Heure locale de l'utilisateur (fuseau tz), et non UTC
                local_now = fields.Datetime.context_timestamp(request.env.user, fields.Datetime.now())
                today = local_now.date()
                # Détermination du créneau : matin (avant 13h) ou après-midi
                current_hour = local_now.hour
                session = 'morning' if current_hour < 13 else 'afternoon'

                # Vérifier si un enregistrement d'assiduité existe déjà pour aujourd'hui
                existing_att = request.env['eacta.attendance'].search([
                    ('student_id', '=', student.id),
                    ('date', '=', today),
                    ('session', '=', session),
                ], limit=1)

                if existing_att:
                    if existing_att.attendance_type != 'present':
                        existing_att.write({'attendance_type': 'present', 'justified': False})
                    attendance_created = existing_att
                else:
                    try:
                        attendance_created = request.env['eacta.attendance'].create({
                            'student_id': student.id,
                            'class_id': student.current_class_id.id if student.current_class_id else False,
                            'date': today,
                            'session': session,
                            'attendance_type': 'present',
                        })
                    except Exception as e:
                        _logger.error("Erreur création assiduité scan: %s", e)
                        error_message = f"Impossible d'enregistrer la présence : {str(e)}"

                if attendance_created:
                    student_data = {
                        'id': student.id,
                        'name': student.name,
                        'code': student.code or '',
                        'class_name': student.current_class_id.name if student.current_class_id else 'Non assigné',
                        'image_url': f"/web/image/eacta.student/{student.id}/image_128",
                        'timestamp': local_now.strftime("%H:%M:%S"),
                        'session': session,
                    }

        # Si requête JSON / API (par exemple via AJAX depuis un scanner de caméra JS)
        if request.httprequest.headers.get('Accept') == 'application/json' or kwargs.get('format') == 'json':
            if error_message:
                return request.make_json_response({'status': 'error', 'message': error_message}, status=400)
            return request.make_json_response({
                'status': 'success',
                'student': student_data,
                'attendance_id': attendance_created.id if attendance_created else False,
            })

        values = {
            'student_data': student_data,
            'attendance_created': attendance_created,
            'error_message': error_message,
            'today': fields.Date.context_today(request.env.user),
        }
        return request.render('eacta_school.attendance_scan_page', values)
