import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from ..models.eacta_notification import (
    sanitize_phone_number,
    build_whatsapp_url,
    format_absence_message,
    format_fee_reminder_message,
    format_grade_message,
)

_logger = logging.getLogger(__name__)


class EactaWhatsappComposer(models.TransientModel):
    _name = 'eacta.whatsapp.composer'
    _description = "Assistant de communication WhatsApp"

    student_id = fields.Many2one('eacta.student', string='Élève concerné')
    recipient_partner_id = fields.Many2one('res.partner', string='Parent / Tuteur destinataire')
    recipient_name = fields.Char(string='Nom du destinataire')
    mobile = fields.Char(string='Numéro WhatsApp / Mobile', required=True)
    message_type = fields.Selection([
        ('absence', 'Alerte Absence / Retard'),
        ('fee', 'Rappel Frais de Scolarité'),
        ('grade', 'Notification de Note'),
        ('custom', 'Message Personnalisé'),
    ], string='Type de message', default='custom', required=True)

    attendance_id = fields.Many2one('eacta.attendance', string='Événement d’assiduité')
    fee_id = fields.Many2one('eacta.student.fee', string='Frais scolaire')
    grade_id = fields.Many2one('eacta.course.grade', string='Note')

    body = fields.Text(string='Contenu du message', required=True)
    preview_url = fields.Char(string='Lien WhatsApp généré', compute='_compute_preview_url')

    @api.depends('mobile', 'body')
    def _compute_preview_url(self):
        ICP = self.env['ir.config_parameter'].sudo()
        prefix = ICP.get_param('eacta_school.whatsapp_country_prefix', '212')
        for wiz in self:
            if wiz.mobile and wiz.body:
                wiz.preview_url = build_whatsapp_url(wiz.mobile, wiz.body, default_country=prefix)
            else:
                wiz.preview_url = False

    @api.onchange('recipient_partner_id')
    def _onchange_recipient_partner_id(self):
        if self.recipient_partner_id:
            self.recipient_name = self.recipient_partner_id.name
            phone = self.recipient_partner_id.mobile or self.recipient_partner_id.phone
            if phone:
                self.mobile = phone

    @api.onchange('message_type')
    def _onchange_message_type(self):
        ICP = self.env['ir.config_parameter'].sudo()
        sig = ICP.get_param('eacta_school.whatsapp_school_signature', 'NR School - Administration & Vie Scolaire')
        if self.message_type == 'absence' and self.attendance_id:
            self.body = format_absence_message(self.attendance_id, signature=sig)
        elif self.message_type == 'fee' and self.fee_id:
            self.body = format_fee_reminder_message(self.fee_id, signature=sig)
        elif self.message_type == 'grade' and self.grade_id:
            self.body = format_grade_message(self.grade_id, signature=sig)
        elif self.message_type == 'custom':
            student_str = f" concernant {self.student_id.name}" if self.student_id else ""
            self.body = f"Bonjour,\n\nMessage de l'établissement scolaire{student_str} :\n\n\n\n— {sig}"

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        ICP = self.env['ir.config_parameter'].sudo()
        sig = ICP.get_param('eacta_school.whatsapp_school_signature', 'NR School - Administration & Vie Scolaire')

        if active_model == 'eacta.attendance' and active_id:
            att = self.env['eacta.attendance'].browse(active_id)
            res['attendance_id'] = att.id
            res['student_id'] = att.student_id.id
            res['message_type'] = 'absence'
            parent = att.student_id.parent_ids[:1]
            if parent:
                res['recipient_partner_id'] = parent.id
                res['recipient_name'] = parent.name
                res['mobile'] = parent.mobile or parent.phone or att.student_id.phone
            else:
                res['recipient_name'] = att.student_id.name
                res['mobile'] = att.student_id.phone
            res['body'] = format_absence_message(att, signature=sig)

        elif active_model == 'eacta.student.fee' and active_id:
            fee = self.env['eacta.student.fee'].browse(active_id)
            res['fee_id'] = fee.id
            res['student_id'] = fee.student_id.id
            res['message_type'] = 'fee'
            parent = fee.parent_id or fee.student_id.parent_ids[:1]
            if parent:
                res['recipient_partner_id'] = parent.id
                res['recipient_name'] = parent.name
                res['mobile'] = parent.mobile or parent.phone or fee.student_id.phone
            else:
                res['recipient_name'] = fee.student_id.name
                res['mobile'] = fee.student_id.phone
            res['body'] = format_fee_reminder_message(fee, signature=sig)

        elif active_model == 'eacta.course.grade' and active_id:
            grade = self.env['eacta.course.grade'].browse(active_id)
            res['grade_id'] = grade.id
            res['student_id'] = grade.student_id.id
            res['message_type'] = 'grade'
            parent = grade.student_id.parent_ids[:1]
            if parent:
                res['recipient_partner_id'] = parent.id
                res['recipient_name'] = parent.name
                res['mobile'] = parent.mobile or parent.phone or grade.student_id.phone
            else:
                res['recipient_name'] = grade.student_id.name
                res['mobile'] = grade.student_id.phone
            res['body'] = format_grade_message(grade, signature=sig)

        elif active_model == 'eacta.student' and active_id:
            student = self.env['eacta.student'].browse(active_id)
            res['student_id'] = student.id
            res['message_type'] = 'custom'
            parent = student.parent_ids[:1]
            if parent:
                res['recipient_partner_id'] = parent.id
                res['recipient_name'] = parent.name
                res['mobile'] = parent.mobile or parent.phone or student.phone
            else:
                res['recipient_name'] = student.name
                res['mobile'] = student.phone
            res['body'] = f"Bonjour,\n\nMessage de l'établissement scolaire concernant {student.name} :\n\n\n\n— {sig}"

        return res

    def action_send_whatsapp(self):
        """Valide, consigne dans le chatter et ouvre l'URL WhatsApp."""
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        prefix = ICP.get_param('eacta_school.whatsapp_country_prefix', '212')
        auto_chatter = ICP.get_param('eacta_school.whatsapp_auto_chatter_log', 'True') in ('True', '1', True)

        clean_phone = sanitize_phone_number(self.mobile, default_country=prefix)
        if not clean_phone:
            raise UserError(_("Le numéro de téléphone « %s » n'est pas un numéro valide.") % self.mobile)

        whatsapp_url = build_whatsapp_url(clean_phone, self.body, default_country=prefix)
        recipient_display = self.recipient_name or self.mobile

        # Traçabilité dans le chatter
        if auto_chatter:
            log_body = (
                f"<p><strong><i class='fa fa-whatsapp text-success'></i> Notification WhatsApp préparée :</strong></p>"
                f"<p><strong>Destinataire :</strong> {recipient_display} ({self.mobile})<br/>"
                f"<strong>Type :</strong> {dict(self._fields['message_type'].selection).get(self.message_type)}</p>"
                f"<blockquote style='border-left: 3px solid #25D366; padding-left: 10px; margin: 5px 0; color: #555;'>"
                f"{self.body.replace(chr(10), '<br/>')}</blockquote>"
            )

            if self.attendance_id:
                self.attendance_id.notification_sent = True
                if self.recipient_partner_id and self.recipient_partner_id not in self.attendance_id.notified_parent_ids:
                    self.attendance_id.notified_parent_ids = [(4, self.recipient_partner_id.id)]
                self.attendance_id.message_post(body=log_body)

            if self.fee_id:
                self.fee_id.reminder_count += 1
                self.fee_id.last_reminder_date = fields.Date.context_today(self)
                self.fee_id.message_post(body=log_body)

            if self.grade_id:
                self.grade_id.message_post(body=log_body)

            if self.student_id:
                self.student_id.message_post(body=log_body)

        return {
            'type': 'ir.actions.act_url',
            'url': whatsapp_url,
            'target': 'new',
        }
