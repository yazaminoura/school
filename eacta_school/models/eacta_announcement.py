from odoo import api, fields, models
from odoo.exceptions import UserError

from .eacta_class import LEVELS


class EactaAnnouncement(models.Model):
    _name = 'eacta.announcement'
    _description = 'Annonce aux familles'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_publish desc, id desc'

    name = fields.Char(string='Objet', required=True, tracking=True)
    body = fields.Html(string='Message', required=True, sanitize_style=True)
    priority = fields.Selection([
        ('normal', 'Information'),
        ('important', 'Important'),
        ('urgent', 'Urgent'),
    ], string='Priorité', default='normal', required=True, tracking=True)
    audience = fields.Selection([
        ('all', "Toute l'école"),
        ('level', 'Un cycle'),
        ('classes', 'Des classes'),
        ('students', 'Des élèves'),
    ], string='Destinataires', default='classes', required=True, tracking=True)
    level = fields.Selection(LEVELS, string='Cycle')
    class_ids = fields.Many2many('eacta.class', string='Classes')
    student_ids = fields.Many2many('eacta.student', string='Élèves')
    target_student_ids = fields.Many2many('eacta.student', 'eacta_announcement_target_student_rel',
                                          'announcement_id', 'student_id', string='Élèves concernés',
                                          compute='_compute_targets', store=True)
    recipient_partner_ids = fields.Many2many('res.partner', 'eacta_announcement_recipient_rel',
                                             'announcement_id', 'partner_id', string='Destinataires (familles)',
                                             compute='_compute_targets', store=True)
    recipient_count = fields.Integer(string='Familles', compute='_compute_targets', store=True)
    send_email = fields.Boolean(string='Envoyer par email', default=True)
    send_sms = fields.Boolean(string='Envoyer par SMS')
    send_whatsapp = fields.Boolean(string='Envoyer par WhatsApp')
    attachment_ids = fields.Many2many('ir.attachment', 'eacta_announcement_attachment_rel', 'announcement_id',
                                      'attachment_id', string='Pièces jointes')
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('published', 'Publiée'),
        ('archived', 'Archivée'),
    ], string='État', default='draft', required=True, tracking=True, index=True)
    date_publish = fields.Datetime(string='Publiée le', readonly=True, copy=False)
    author_id = fields.Many2one('res.users', string='Auteur', default=lambda self: self.env.user, readonly=True)
    read_ids = fields.One2many('eacta.announcement.read', 'announcement_id', string='Lectures')
    read_count = fields.Integer(string='Lues', compute='_compute_read_stats')
    read_rate = fields.Float(string='Taux de lecture (%)', compute='_compute_read_stats', digits=(5, 1))
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.depends('audience', 'level', 'class_ids', 'student_ids', 'class_ids.student_ids',
                 'class_ids.student_ids.parent_ids', 'student_ids.parent_ids')
    def _compute_targets(self):
        Student = self.env['eacta.student'].sudo()
        for announcement in self:
            if announcement.audience == 'all':
                students = Student.search([('state', 'in', ('draft', 'enrolled'))])
            elif announcement.audience == 'level':
                year = self.env['eacta.academic.year'].sudo().get_current_year()
                classes = self.env['eacta.class'].sudo().search([
                    ('level', '=', announcement.level), ('academic_year_id', '=', year.id)]) if year                     else self.env['eacta.class']
                students = classes.student_ids
            elif announcement.audience == 'classes':
                students = announcement.class_ids.sudo().student_ids
            else:
                students = announcement.student_ids.sudo()
            students = students.filtered(lambda s: s.state in ('draft', 'enrolled'))
            partners = students.parent_ids | students.partner_id
            announcement.target_student_ids = [(6, 0, students.ids)]
            announcement.recipient_partner_ids = [(6, 0, partners.ids)]
            announcement.recipient_count = len(partners)

    @api.depends('read_ids', 'recipient_count')
    def _compute_read_stats(self):
        for announcement in self:
            announcement.read_count = len(announcement.read_ids)
            announcement.read_rate = round(100.0 * announcement.read_count / announcement.recipient_count, 1) \
                if announcement.recipient_count else 0.0

    def action_publish(self):
        Channel = self.env['eacta.notification.channel']
        for announcement in self:
            if announcement.state != 'draft':
                raise UserError(f"« {announcement.name} » est déjà publiée.")
            announcement._compute_targets()
            if not announcement.recipient_partner_ids:
                raise UserError(f"Aucune famille ne correspond aux destinataires de « {announcement.name} ».")
            announcement.write({'state': 'published', 'date_publish': fields.Datetime.now()})
            partners = announcement.recipient_partner_ids
            if announcement.send_email:
                mail_partners = partners.filtered('email')
                announcement.message_post(
                    body=announcement.body,
                    subject=announcement.name,
                    partner_ids=mail_partners.ids,
                    attachment_ids=announcement.attachment_ids.ids,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
            for channel, enabled in (('sms', announcement.send_sms), ('whatsapp', announcement.send_whatsapp)):
                if enabled:
                    sent = sum(1 for partner in partners
                               if Channel.send_notification(channel, partner, False, announcement._name,
                                                            announcement.id))
                    announcement.message_post(body=f"Annonce transmise par {channel.upper()} à {sent} famille(s).")

    def action_archive_announcement(self):
        self.write({'state': 'archived'})

    def action_draft(self):
        self.write({'state': 'draft', 'date_publish': False})

    def _mark_read(self, partner):
        """Enregistre la lecture d'une annonce par une famille (appelé depuis le portail)."""
        Read = self.env['eacta.announcement.read'].sudo()
        for announcement in self:
            if not Read.search_count([('announcement_id', '=', announcement.id), ('partner_id', '=', partner.id)]):
                Read.create({'announcement_id': announcement.id, 'partner_id': partner.id})

    def action_view_reads(self):
        self.ensure_one()
        return {
            'name': f"Lectures - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.announcement.read',
            'view_mode': 'list',
            'domain': [('announcement_id', '=', self.id)],
        }


class EactaAnnouncementRead(models.Model):
    _name = 'eacta.announcement.read'
    _description = "Accusé de lecture d'annonce"
    _order = 'read_date desc'

    announcement_id = fields.Many2one('eacta.announcement', string='Annonce', required=True, ondelete='cascade',
                                      index=True)
    partner_id = fields.Many2one('res.partner', string='Lue par', required=True, ondelete='cascade', index=True)
    read_date = fields.Datetime(string='Lue le', default=fields.Datetime.now, required=True)

    _sql_constraints = [
        ('announcement_partner_unique', 'UNIQUE(announcement_id, partner_id)',
         "Cette annonce est déjà marquée comme lue par ce contact."),
    ]
