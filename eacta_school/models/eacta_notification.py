import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class EactaNotificationChannel(models.AbstractModel):
    _name = 'eacta.notification.channel'
    _description = 'Canal de notification (Extension multicanale)'

    @api.model
    def send_notification(self, channel_type, recipient_partner, template_xml_id, res_model, res_id, **kwargs):
        """
        Point d'extension unifié pour l'envoi de notifications aux familles.
        Canaux supportés :
        - email (opérationnel avec mail.template)
        - sms (extension abstraite prête pour intégration passerelle)
        - whatsapp (extension abstraite prête pour Cloud API / Twilio)
        """
        if channel_type == 'email':
            return self._send_email(recipient_partner, template_xml_id, res_model, res_id, **kwargs)
        elif channel_type == 'sms':
            return self._send_sms(recipient_partner, res_model, res_id, **kwargs)
        elif channel_type == 'whatsapp':
            return self._send_whatsapp(recipient_partner, res_model, res_id, **kwargs)
        else:
            _logger.warning("Canal de notification non supporté : %s", channel_type)
            return False

    @api.model
    def _send_email(self, recipient_partner, template_xml_id, res_model, res_id, **kwargs):
        """Envoi par email via le template QWeb mail."""
        if not recipient_partner or not recipient_partner.email:
            _logger.debug("Aucun email valide pour le partenaire %s", recipient_partner.name if recipient_partner else 'Inconnu')
            return False
        template = self.env.ref(template_xml_id, raise_if_not_found=False)
        if not template:
            _logger.warning("Template mail introuvable : %s", template_xml_id)
            return False
        try:
            force_send = kwargs.get('force_send', True)
            email_values = {
                'email_to': recipient_partner.email,
                'recipient_ids': [(4, recipient_partner.id)],
            }
            mail_id = template.send_mail(res_id, force_send=force_send, email_values=email_values)
            return bool(mail_id)
        except Exception as e:
            _logger.warning("Échec de l'envoi de notification email à %s: %s", recipient_partner.email, e)
            return False

    @api.model
    def _send_sms(self, recipient_partner, res_model, res_id, **kwargs):
        """Point d'extension pour les alertes SMS."""
        phone = recipient_partner.phone or recipient_partner.mobile
        if not phone:
            return False
        _logger.info("Extension SMS active : notification préparée pour %s (%s)", recipient_partner.name, phone)
        # Prêt pour raccordement à un fournisseur SMS (ex. Infobip, Twilio, Odoo IAP)
        return True

    @api.model
    def _send_whatsapp(self, recipient_partner, res_model, res_id, **kwargs):
        """Point d'extension pour les alertes WhatsApp."""
        phone = recipient_partner.mobile or recipient_partner.phone
        if not phone:
            return False
        _logger.info("Extension WhatsApp active : notification préparée pour %s (%s)", recipient_partner.name, phone)
        # Prêt pour raccordement à l'API Meta WhatsApp Business
        return True
