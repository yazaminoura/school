from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ------------------------------------------------------------------
    # Coefficients des types d'examens
    # ------------------------------------------------------------------
    weight_quiz = fields.Float(
        string='Poids - Contrôle continu', default=1.0,
        config_parameter='eacta_school.weight_quiz')
    weight_homework = fields.Float(
        string='Poids - Devoir surveillé', default=1.0,
        config_parameter='eacta_school.weight_homework')
    weight_oral = fields.Float(
        string='Poids - Épreuve orale', default=1.0,
        config_parameter='eacta_school.weight_oral')
    weight_practical = fields.Float(
        string='Poids - Travaux pratiques', default=1.0,
        config_parameter='eacta_school.weight_practical')
    weight_midterm = fields.Float(
        string='Poids - Examen partiel', default=2.0,
        config_parameter='eacta_school.weight_midterm')
    weight_final = fields.Float(
        string='Poids - Examen final', default=3.0,
        config_parameter='eacta_school.weight_final')

    # ------------------------------------------------------------------
    # Politique des absences aux examens
    # ------------------------------------------------------------------
    absent_policy = fields.Selection([
        ('excluded', 'Exclu de la moyenne'),
        ('zero', 'Compte comme 0/20'),
        ('retake', 'Session de rattrapage requise'),
    ], string="Politique d'absence aux examens", default='excluded',
       config_parameter='eacta_school.absent_policy')
    unjustified_absence_zero = fields.Boolean(
        string="Compter les absences injustifiées comme 0/20", default=True,
        config_parameter='eacta_school.unjustified_absence_zero',
        help="Si activé, toute absence non justifiée est comptabilisée avec la note zéro.")

    # ------------------------------------------------------------------
    # Alertes assiduité
    # ------------------------------------------------------------------
    unjustified_absence_threshold = fields.Integer(
        string="Seuil d'alerte absences non justifiées (par mois)", default=3,
        config_parameter='eacta_school.unjustified_absence_threshold',
        help="Déclenche une activité pour le professeur principal et une alerte sur la fiche de l'élève")
    send_absence_parent_email = fields.Boolean(
        string="Notifier les parents par email lors du dépassement de seuil", default=True,
        config_parameter='eacta_school.send_absence_parent_email')

    # ------------------------------------------------------------------
    # Frais de scolarité & pénalités
    # ------------------------------------------------------------------
    enable_late_fee = fields.Boolean(
        string="Appliquer une pénalité de retard", default=False,
        config_parameter='eacta_school.enable_late_fee')
    late_fee_type = fields.Selection([
        ('fixed', 'Montant fixe'),
        ('percent', 'Pourcentage du reste dû'),
    ], string="Type de pénalité", default='fixed',
       config_parameter='eacta_school.late_fee_type')
    late_fee_amount = fields.Float(
        string="Montant / Taux de la pénalité", default=50.0,
        config_parameter='eacta_school.late_fee_amount')

    enable_sibling_discount = fields.Boolean(
        string="Activer la remise fratrie", default=False,
        config_parameter='eacta_school.enable_sibling_discount')
    sibling_discount_rate = fields.Float(
        string="Taux de remise fratrie (%)", default=10.0,
        config_parameter='eacta_school.sibling_discount_rate')

    # ------------------------------------------------------------------
    # Moyenne d'admission
    # ------------------------------------------------------------------
    pass_mark = fields.Float(
        string="Seuil de passage / admission (/20)", default=10.0,
        config_parameter='eacta_school.pass_mark')
