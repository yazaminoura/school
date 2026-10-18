from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

LANGUAGES = [
    ('fr', 'Français'),
    ('ar', 'Arabe'),
    ('en', 'Anglais'),
    ('es', 'Espagnol'),
    ('amz', 'Amazigh'),
    ('other', 'Autre'),
]


class LibraryBookCategory(models.Model):
    _name = 'library.book.category'
    _description = 'Catégorie de livres'
    _order = 'name'

    name = fields.Char(string='Nom', required=True, translate=True)
    color = fields.Integer(string='Couleur')
    description = fields.Text(string='Description')
    book_ids = fields.One2many('library.book', 'category_id', string='Livres')
    book_count = fields.Integer(string='Titres', compute='_compute_book_stats')
    copy_count = fields.Integer(string='Exemplaires', compute='_compute_book_stats')
    available_book_count = fields.Integer(string='Exemplaires disponibles', compute='_compute_book_stats')

    @api.depends('book_ids.total_quantity', 'book_ids.available_quantity')
    def _compute_book_stats(self):
        for category in self:
            category.book_count = len(category.book_ids)
            category.copy_count = sum(category.book_ids.mapped('total_quantity'))
            category.available_book_count = sum(category.book_ids.mapped('available_quantity'))

    def action_view_books(self):
        self.ensure_one()
        return {
            'name': self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'library.book',
            'view_mode': 'kanban,list,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id},
        }


class LibraryBook(models.Model):
    _name = 'library.book'
    _description = 'Livre'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Titre', required=True, tracking=True, translate=True)
    author = fields.Char(string='Auteur', tracking=True, translate=True)
    isbn = fields.Char(string='ISBN', tracking=True, copy=False)
    publisher = fields.Char(string='Éditeur')
    publication_year = fields.Integer(string='Année de publication')
    edition = fields.Char(string='Édition')
    language = fields.Selection(LANGUAGES, string='Langue', default='fr')
    pages = fields.Integer(string='Pages')
    shelf_location = fields.Char(string='Emplacement (cote)', help="Rayon / étagère, ex : B-12")
    description = fields.Text(string='Résumé', translate=True)
    category_id = fields.Many2one('library.book.category', string='Catégorie', tracking=True)
    image = fields.Binary(string='Couverture', attachment=True)
    color = fields.Integer(string='Couleur')
    active = fields.Boolean(default=True)

    barcode_ids = fields.One2many('library.book.barcode', 'book_id', string='Exemplaires')
    total_quantity = fields.Integer(
        string="Nombre d'exemplaires", compute='_compute_quantities', store=True, readonly=False, tracking=True,
        help="Modifier ce nombre crée ou retire automatiquement des exemplaires.")
    available_quantity = fields.Integer(string='Disponibles', compute='_compute_quantities', store=True)
    on_loan_quantity = fields.Integer(string='Empruntés', compute='_compute_quantities', store=True)
    is_available = fields.Boolean(string='Disponible', compute='_compute_quantities', store=True)
    status = fields.Selection([
        ('available', 'Disponible'),
        ('on_loan', 'Tous empruntés'),
    ], string='Statut', compute='_compute_quantities', store=True)
    loan_duration_days = fields.Integer(string="Durée de prêt (jours)", default=14, tracking=True)
    replacement_cost = fields.Float(string="Frais en cas de perte", default=100.0, digits=(10, 2), tracking=True)

    loan_ids = fields.One2many('library.loan', 'book_id', string='Emprunts')
    loan_count = fields.Integer(string="Nombre d'emprunts", compute='_compute_loan_count')

    _sql_constraints = [
        ('isbn_unique', 'UNIQUE(isbn)', "Un autre livre possède déjà cet ISBN."),
        ('loan_duration_positive', 'CHECK(loan_duration_days > 0)', "La durée de prêt doit être positive."),
    ]

    @api.depends('barcode_ids', 'barcode_ids.state')
    def _compute_quantities(self):
        for book in self:
            copies = book.barcode_ids.filtered(lambda c: c.state != 'lost')
            available = copies.filtered(lambda c: c.state == 'available')
            book.total_quantity = len(copies)
            book.available_quantity = len(available)
            book.on_loan_quantity = len(copies) - len(available)
            book.is_available = bool(available)
            book.status = 'available' if available else 'on_loan'

    def _compute_loan_count(self):
        data = self.env['library.loan']._read_group([('book_id', 'in', self.ids)], ['book_id'], ['__count'])
        counts = {book.id: count for book, count in data}
        for book in self:
            book.loan_count = counts.get(book.id, 0)

    @api.depends('name', 'author')
    def _compute_display_name(self):
        for book in self:
            book.display_name = f"{book.name} — {book.author}" if book.author else book.name

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        domain = list(domain or [])
        if name:
            domain = ['|', '|', ('name', operator, name), ('author', operator, name), ('isbn', operator, name)] + domain
        return self._search(domain, limit=limit, order=order)

    # ------------------------------------------------------------------
    # Exemplaires
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        wanted = [vals.get('total_quantity') for vals in vals_list]
        books = super().create(vals_list)
        for book, qty, vals in zip(books, wanted, vals_list):
            if 'barcode_ids' not in vals:
                book._sync_copies(qty if qty is not None else 1)
        return books

    def write(self, vals):
        qty = vals.get('total_quantity')
        res = super().write(vals)
        if qty is not None and 'barcode_ids' not in vals:
            for book in self:
                book._sync_copies(qty)
        return res

    def _sync_copies(self, quantity):
        """Ajuste le nombre d'exemplaires (non perdus) à ``quantity``."""
        self.ensure_one()
        if quantity < 0:
            raise ValidationError("Le nombre d'exemplaires ne peut pas être négatif.")
        copies = self.barcode_ids.filtered(lambda c: c.state != 'lost')
        if quantity > len(copies):
            self.env['library.book.barcode'].create([{'book_id': self.id} for _i in range(quantity - len(copies))])
        elif quantity < len(copies):
            removable = copies.filtered(lambda c: c.state == 'available' and not c.loan_ids)
            to_remove = len(copies) - quantity
            if len(removable) < to_remove:
                raise UserError(
                    f"Impossible de retirer {to_remove} exemplaire(s) de « {self.name} » : "
                    "seuls les exemplaires disponibles et jamais empruntés peuvent être supprimés. "
                    "Archivez ou déclarez perdus les autres exemplaires.")
            removable.sorted('id', reverse=True)[:to_remove].unlink()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_borrow(self):
        self.ensure_one()
        copy = self.barcode_ids.filtered(lambda c: c.state == 'available')[:1]
        if not copy:
            next_return = self.loan_ids.filtered(lambda l: l.state in ('ongoing', 'overdue')).sorted('due_date')[:1]
            hint = f" Prochain retour prévu le {next_return.due_date.strftime('%d/%m/%Y')}." if next_return else ''
            raise UserError(f"Aucun exemplaire de « {self.name} » n'est disponible.{hint}")
        return {
            'name': f"Guichet Express - Emprunter « {self.name} »",
            'type': 'ir.actions.act_window',
            'res_model': 'library.desk.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_mode': 'checkout',
                'default_book_id': self.id,
                'default_barcode_id': copy.id,
                'default_borrower_type': 'student',
            },
        }

    def action_view_loans(self):
        self.ensure_one()
        return {
            'name': f"Emprunts - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'library.loan',
            'view_mode': 'list,kanban,form',
            'domain': [('book_id', '=', self.id)],
            'context': {'default_book_id': self.id},
        }

    def action_view_copies(self):
        self.ensure_one()
        return {
            'name': f"Exemplaires - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'library.book.barcode',
            'view_mode': 'list,form',
            'domain': [('book_id', '=', self.id)],
            'context': {'default_book_id': self.id},
        }

    def action_print_labels(self):
        return self.env.ref('eacta_bibliotheque.action_report_copy_labels').report_action(self.barcode_ids)

    # Compatibilité avec l'ancien bouton
    def action_generate_barcodes(self):
        for book in self:
            book._sync_copies(book.total_quantity)
        return True


class LibraryBookBarcode(models.Model):
    _name = 'library.book.barcode'
    _description = 'Exemplaire'
    _rec_name = 'barcode'
    _order = 'book_id, barcode'

    book_id = fields.Many2one('library.book', string='Livre', required=True, ondelete='cascade', index=True)
    barcode = fields.Char(string='Code-barres', required=True, copy=False, index=True)
    manual_barcode = fields.Char(string='Code-barres manuel', help="Remplace le code-barres généré")
    condition = fields.Selection([
        ('new', 'Neuf'),
        ('good', 'Bon état'),
        ('worn', 'Usé'),
        ('damaged', 'Abîmé'),
    ], string='État physique', default='good')
    acquisition_date = fields.Date(string="Date d'acquisition", default=fields.Date.context_today)
    loan_ids = fields.One2many('library.loan', 'barcode_id', string='Historique des emprunts')
    current_loan_id = fields.Many2one('library.loan', string='Emprunt en cours', compute='_compute_state', store=True)
    state = fields.Selection([
        ('available', 'Disponible'),
        ('on_loan', 'Emprunté'),
        ('lost', 'Perdu'),
    ], string='Statut', compute='_compute_state', store=True)
    is_available = fields.Boolean(string='Disponible', compute='_compute_state', store=True)
    borrower_name = fields.Char(string='Emprunteur', related='current_loan_id.borrower_name')
    due_date = fields.Date(string='Retour prévu', related='current_loan_id.due_date')

    _sql_constraints = [
        ('barcode_unique', 'UNIQUE(barcode)', "Ce code-barres est déjà utilisé par un autre exemplaire."),
    ]

    @api.depends('loan_ids.state')
    def _compute_state(self):
        for copy in self:
            loans = copy.loan_ids
            active = loans.filtered(lambda l: l.state in ('ongoing', 'overdue'))[:1]
            lost = loans.filtered(lambda l: l.state == 'lost')
            copy.current_loan_id = active
            copy.state = 'on_loan' if active else ('lost' if lost else 'available')
            copy.is_available = copy.state == 'available'

    @api.constrains('barcode')
    def _check_barcode(self):
        allowed = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-')
        for copy in self:
            if len(copy.barcode) < 4:
                raise ValidationError("Le code-barres doit contenir au moins 4 caractères.")
            if not set(copy.barcode) <= allowed:
                raise ValidationError("Le code-barres ne peut contenir que des lettres, chiffres et tirets.")

    def _next_barcode(self, book, taken):
        prefix = (book.isbn or f"LIV{book.id:05d}").replace(' ', '')
        n = len(book.barcode_ids) + 1
        while True:
            code = f"{prefix}-{n:03d}"
            if code not in taken and not self.search_count([('barcode', '=', code)]):
                taken.add(code)
                return code
            n += 1

    @api.model_create_multi
    def create(self, vals_list):
        taken = set()
        for vals in vals_list:
            if vals.get('manual_barcode'):
                vals['barcode'] = vals['manual_barcode']
            elif not vals.get('barcode') and vals.get('book_id'):
                vals['barcode'] = self._next_barcode(self.env['library.book'].browse(vals['book_id']), taken)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('manual_barcode'):
            vals['barcode'] = vals['manual_barcode']
        return super().write(vals)

    def action_view_loans(self):
        self.ensure_one()
        return {
            'name': f"Historique - {self.barcode}",
            'type': 'ir.actions.act_window',
            'res_model': 'library.loan',
            'view_mode': 'list,form',
            'domain': [('barcode_id', '=', self.id)],
        }

    def action_desk_checkout(self):
        self.ensure_one()
        return {
            'name': f"Prêter {self.barcode}",
            'type': 'ir.actions.act_window',
            'res_model': 'library.desk.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_mode': 'checkout',
                'default_barcode_id': self.id,
            },
        }

    def action_desk_return(self):
        self.ensure_one()
        return {
            'name': f"Retour {self.barcode}",
            'type': 'ir.actions.act_window',
            'res_model': 'library.desk.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_mode': 'return',
                'default_return_barcode_id': self.id,
            },
        }
