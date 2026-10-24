import logging
import re
import urllib.parse
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def sanitize_phone_number(phone, default_country='212'):
    """
    Nettoie et formate un numéro de téléphone en format international E.164 (sans +)
    optimisé pour les liens WhatsApp wa.me/<numéro>.
    Exemples (avec Maroc 212 par défaut) :
      '06 12 34 56 78' -> '212612345678'
      '07-11-22-33-44' -> '212711223344'
      '+212 612 345 678' -> '212612345678'
      '00212612345678' -> '212612345678'
      '0522123456' -> '212522123456'
    """
    if not phone:
        return False
    # Supprimer les caractères non numériques
    cleaned = re.sub(r'[^\d+]', '', str(phone).strip())
    if cleaned.startswith('+'):
        cleaned = cleaned[1:]
    elif cleaned.startswith('00'):
        cleaned = cleaned[2:]

    # Numéro local marocain à 10 chiffres commençant par 0 (ex. 06..., 07..., 05...)
    if cleaned.startswith('0') and len(cleaned) == 10:
        cleaned = default_country + cleaned[1:]
    # Numéro à 9 chiffres sans le zéro initial
    elif len(cleaned) == 9 and not cleaned.startswith(default_country):
        cleaned = default_country + cleaned

    return cleaned if len(cleaned) >= 8 else False


def build_whatsapp_url(phone, message, default_country='212'):
    """Génère l'URL d'action WhatsApp Web / Mobile wa.me."""
    clean_phone = sanitize_phone_number(phone, default_country)
    if not clean_phone:
        return False
    encoded_text = urllib.parse.quote(message)
    return f"https://wa.me/{clean_phone}?text={encoded_text}"


def format_absence_message(attendance, signature="Vie Scolaire - NR School"):
    """Prépare le texte courtois de notification d'absence ou de retard."""
    student_name = attendance.student_id.name or "votre enfant"
    klass_name = attendance.class_id.name or attendance.student_id.current_class_id.name or ""
    klass_str = f" ({klass_name})" if klass_name else ""
    date_str = attendance.date.strftime("%d/%m/%Y") if attendance.date else ""
    session_labels = {'morning': 'Matin', 'afternoon': 'Après-midi', 'all_day': 'Journée entière'}
    session_str = session_labels.get(attendance.session, attendance.session or "")
    type_labels = {'absent': 'absent(e)', 'late': 'en retard', 'present': 'présent(e)'}
    type_str = type_labels.get(attendance.attendance_type, attendance.attendance_type)
    course_str = f" en cours de {attendance.course_id.name}" if attendance.course_id else ""

    msg = (
        f"Bonjour,\n\n"
        f"L'établissement scolaire vous informe que l'élève {student_name}{klass_str} "
        f"a été marqué(e) {type_str} le {date_str} ({session_str}){course_str}.\n\n"
    )
    if attendance.justified:
        msg += "Statut : Justifié(e).\n"
    else:
        msg += "Statut : Non justifié(e). Merci de bien vouloir fournir un justificatif auprès de la vie scolaire.\n\n"
    if signature:
        msg += f"— {signature}"
    return msg


def format_fee_reminder_message(fee, signature="Service Comptabilité - NR School"):
    """Prépare le texte courtois de relance pour frais scolaires en attente."""
    student_name = fee.student_id.name or "votre enfant"
    klass_name = fee.class_id.name or fee.student_id.current_class_id.name or ""
    klass_str = f" ({klass_name})" if klass_name else ""
    fee_type = fee.description or fee.fee_type_id.name or "Frais scolaires"
    due_date = fee.due_date.strftime("%d/%m/%Y") if fee.due_date else ""
    amount_due = f"{fee.amount_due:.2f} {fee.currency_id.symbol or 'MAD'}"

    msg = (
        f"Bonjour,\n\n"
        f"Rappel de scolarité concernant {student_name}{klass_str} :\n"
        f"L'échéance « {fee_type} » présente un solde restant dû de {amount_due} "
        f"(échéance fixée au {due_date}).\n\n"
        f"Nous vous remercions de bien vouloir régulariser ce règlement auprès de l'administration scolaire.\n\n"
    )
    if signature:
        msg += f"— {signature}"
    return msg


def format_grade_message(grade_rec, signature="Direction Pédagogique - NR School"):
    """Prépare le message de publication de note pour un élève."""
    from .eacta_course_grade import APPRECIATIONS
    student_name = grade_rec.student_id.name or "votre enfant"
    klass_name = grade_rec.class_id.name or grade_rec.student_id.current_class_id.name or ""
    klass_str = f" ({klass_name})" if klass_name else ""
    course_name = grade_rec.course_id.name or "Matière"
    exam_name = grade_rec.exam_id.name or "Évaluation"
    appr_dict = dict(APPRECIATIONS)
    appr_str = appr_dict.get(grade_rec.appreciation, "")
    appr_part = f" — Mention : {appr_str}" if appr_str else ""

    if grade_rec.status == 'graded':
        grade_text = f"{grade_rec.grade:.2f}/20{appr_part}"
    elif grade_rec.status == 'absent':
        grade_text = "Absent(e) à l'examen"
    elif grade_rec.status == 'exempt':
        grade_text = "Dispensé(e)"
    else:
        grade_text = "En cours d'évaluation"

    msg = (
        f"Bonjour,\n\n"
        f"La note de l'élève {student_name}{klass_str} pour l'évaluation "
        f"« {exam_name} » ({course_name}) a été enregistrée :\n"
        f"Résultat : {grade_text}\n\n"
    )
    if grade_rec.comment:
        msg += f"Observation : {grade_rec.comment}\n\n"
    if signature:
        msg += f"— {signature}"
    return msg


class EactaNotificationChannel(models.AbstractModel):
    _name = 'eacta.notification.channel'
    _description = 'Canal de notification (Extension multicanale)'

    @api.model
    def send_notification(self, channel_type, recipient_partner, template_xml_id, res_model, res_id, **kwargs):
        """
        Point d'extension unifié pour l'envoi de notifications aux familles.
        Canaux supportés :
        - email (opérationnel avec mail.template)
        - sms (extension abstraite prête pour passerelle)
        - whatsapp (génération d'action wa.me et extension API Cloud)
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
        phone = recipient_partner.mobile or recipient_partner.phone if recipient_partner else kwargs.get('phone')
        if not phone:
            return False
        _logger.info("Extension SMS : notification préparée pour %s (%s)", recipient_partner.name if recipient_partner else 'Contact', phone)
        return True

    @api.model
    def _send_whatsapp(self, recipient_partner, res_model, res_id, **kwargs):
        """Point d'extension pour les alertes WhatsApp."""
        phone = recipient_partner.mobile or recipient_partner.phone if recipient_partner else kwargs.get('phone')
        if not phone:
            return False
        message = kwargs.get('message', '')
        url = build_whatsapp_url(phone, message)
        _logger.info("Extension WhatsApp : URL préparée pour %s (%s)", recipient_partner.name if recipient_partner else 'Contact', url)
        return url
