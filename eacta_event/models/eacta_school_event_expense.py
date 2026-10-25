from odoo import api, fields, models


class EactaSchoolEventExpense(models.Model):
    _name = 'eacta.school.event.expense'
    _description = "Dépense liée à un événement scolaire"
    _order = 'payment_date desc, id desc'

    event_id = fields.Many2one('eacta.school.event', string='Événement', required=True, ondelete='cascade',
                               index=True)
    name = fields.Char(string='Désignation', required=True)
    expense_type = fields.Selection([
        ('transport', 'Transport & Déplacements'),
        ('tickets', 'Billetterie & Entrées'),
        ('catering', 'Restauration & Goûter'),
        ('lodging', 'Hébergement'),
        ('equipment', 'Matériel & Équipement'),
        ('insurance', 'Assurance spécifique'),
        ('guide', 'Guide / Intervenant externe'),
        ('other', 'Autre dépense'),
    ], string='Type de dépense', default='other', required=True)
    amount = fields.Monetary(string='Montant', required=True, currency_field='currency_id')
    currency_id = fields.Many2one(related='event_id.currency_id')
    vendor = fields.Char(string='Prestataire / Fournisseur')
    payment_date = fields.Date(string='Date de règlement', default=fields.Date.context_today)
    state = fields.Selection([
        ('planned', 'Prévue'),
        ('paid', 'Payée'),
        ('cancelled', 'Annulée'),
    ], string='État', default='paid', required=True)
    notes = fields.Text(string='Notes / Justificatif')
    company_id = fields.Many2one(related='event_id.company_id', store=True, readonly=True)
