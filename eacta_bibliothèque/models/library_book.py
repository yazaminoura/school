from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class LibraryBook(models.Model):
    _name = 'library.book'
    _description = 'Library Book'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # MULTI-LANGUAGE: Translatable fields
    name = fields.Char(string='Title', required=True, tracking=True, translate=True)
    author = fields.Char(string='Author', tracking=True, translate=True)
    isbn = fields.Char(string='ISBN', required=True)
    description = fields.Text(string='Description', translate=True)
    category_id = fields.Many2one('library.book.category', string='Category', tracking=True)
    status = fields.Selection(
        [('available', 'Available'), ('on_loan', 'Borrowed')],
        string='Status', default='available', required=True, tracking=True
    )
    loan_ids = fields.One2many('library.loan', 'book_id', string='Loans')
    image = fields.Binary(string='Cover Image', attachment=True)
    barcode_ids = fields.One2many('library.book.barcode', 'book_id', string='Barcodes')
    total_quantity = fields.Integer(string='Total Quantity', default=1, tracking=True, required=True)
    available_quantity = fields.Integer(string='Available Quantity', compute='_compute_available_quantity', store=True)
    is_available = fields.Boolean(string='Available', compute='_compute_is_available', store=True)
    loan_duration_days = fields.Integer(string="Loan Duration (days)", default=7, tracking=True)

    @api.depends('total_quantity', 'loan_ids.returned')
    def _compute_available_quantity(self):
        for book in self:
            non_returned_loans_count = len(book.loan_ids.filtered(lambda l: not l.returned))
            book.available_quantity = book.total_quantity - non_returned_loans_count

    @api.depends('available_quantity')
    def _compute_is_available(self):
        for record in self:
            record.is_available = record.available_quantity > 0

    @api.constrains('total_quantity', 'barcode_ids')
    def _check_quantity_and_barcodes(self):
        for book in self:
            if book.total_quantity < 1:
                raise ValidationError("Total quantity must be at least 1.")
            barcode_count = len(book.barcode_ids)
            if barcode_count != book.total_quantity:
                raise ValidationError(
                    f"Number of barcodes ({barcode_count}) must match total quantity ({book.total_quantity})."
                )

    @api.model
    def create(self, vals):
        book = super(LibraryBook, self).create(vals)
        if 'total_quantity' in vals and 'barcode_ids' not in vals and vals.get('total_quantity', 0) > 0:
            barcode_vals = []
            for i in range(vals['total_quantity']):
                barcode_vals.append((0, 0, {
                    'barcode': f"{vals.get('isbn', 'BOOK')}-{i + 1:03d}"
                }))
            book.write({'barcode_ids': barcode_vals})
        return book

    def write(self, vals):
        result = super(LibraryBook, self).write(vals)
        if 'total_quantity' in vals or 'barcode_ids' in vals:
            for book in self:
                barcode_count = len(book.barcode_ids)
                if barcode_count != book.total_quantity:
                    raise ValidationError(
                        f"Number of barcodes ({barcode_count}) must match total quantity ({book.total_quantity})."
                    )
        return result

    def action_borrow(self):
        for book in self:
            if book.is_available:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'library.loan',
                    'view_mode': 'form',
                    'view_id': self.env.ref('eacta_bibliothèque.view_library_loan_form').id,
                    'target': 'new',
                    'context': {
                        'default_book_id': book.id,
                        'default_checkout_date': fields.Date.today(),
                        'default_due_date': fields.Date.add(fields.Date.today(), days=book.loan_duration_days),
                    },
                }
            else:
                active_loans = self.env['library.loan'].search([
                    ('book_id', '=', book.id),
                    ('returned', '=', False)
                ], order='due_date ASC')
                if active_loans:
                    earliest_due_date = active_loans[0].due_date.strftime('%d/%m/%Y')
                    raise UserError(
                        f"Book '{book.name}' is unavailable. Earliest due date: {earliest_due_date}."
                    )
                else:
                    raise UserError(f"Book '{book.name}' is unavailable.")

    def action_generate_barcodes(self):
        for book in self:
            if book.total_quantity > len(book.barcode_ids):
                book.barcode_ids = [(5, 0, 0)]
                barcode_vals = []
                for i in range(book.total_quantity):
                    barcode_vals.append((0, 0, {
                        'barcode': f"{book.isbn}-{i + 1:03d}"
                    }))
                book.write({'barcode_ids': barcode_vals})
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Barcodes Generated',
                        'message': f'{book.total_quantity} barcodes generated for {book.name}.',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError("Barcode count already matches total quantity.")


class LibraryBookBarcode(models.Model):
    _name = 'library.book.barcode'
    _description = 'Library Book Barcode'
    _rec_name = 'barcode'

    book_id = fields.Many2one('library.book', string='Book', required=True, ondelete='cascade')
    barcode = fields.Char(string='Barcode', required=True)
    manual_barcode = fields.Char(string='Manual Barcode', help="Type barcode manually")  # NEW: Manual barcode field
    is_available = fields.Boolean(string="Available", compute="_compute_is_available", store=True)
    icon_status = fields.Html(string="✅/❌ Status", compute="_compute_icon_status", sanitize=False)

    @api.depends()
    def _compute_is_available(self):
        for rec in self:
            active_loan = self.env['library.loan'].search([
                ('barcode_id', '=', rec.id),
                ('returned', '=', False)
            ], limit=1)
            rec.is_available = not bool(active_loan)

    @api.depends('is_available')
    def _compute_icon_status(self):
        for rec in self:
            if rec.is_available:
                rec.icon_status = '<span style="color:green; font-size:16px;">✅ Available</span>'
            else:
                rec.icon_status = '<span style="color:red; font-size:16px;">❌ Borrowed</span>'

    @api.constrains('barcode', 'manual_barcode')
    def _check_barcode(self):
        for barcode in self:
            # Use manual barcode if provided, otherwise use auto-generated
            effective_barcode = barcode.manual_barcode or barcode.barcode

            if effective_barcode:
                if len(effective_barcode) <= 4:
                    raise ValidationError("Barcode must contain more than 4 characters.")
                allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-')
                if not all(char in allowed_chars for char in effective_barcode):
                    raise ValidationError("Barcode must contain only alphanumeric characters and hyphens.")
                existing_barcodes = self.env['library.book.barcode'].search([
                    ('barcode', '=', effective_barcode),
                    ('id', '!=', barcode.id)
                ])
                if existing_barcodes:
                    raise ValidationError(f"Barcode '{effective_barcode}' must be unique.")

    @api.model
    def create(self, vals):
        # Prefer manual barcode if provided
        if 'manual_barcode' in vals and vals['manual_barcode']:
            vals['barcode'] = vals['manual_barcode']
        elif 'barcode' not in vals or not vals['barcode']:
            book = self.env['library.book'].browse(vals.get('book_id'))
            if book:
                existing_count = self.search_count([('book_id', '=', book.id)])
                vals['barcode'] = f"{book.isbn}-{existing_count + 1:03d}"
        return super(LibraryBookBarcode, self).create(vals)

    def write(self, vals):
        # Update barcode if manual_barcode is changed
        if 'manual_barcode' in vals:
            if vals['manual_barcode']:
                vals['barcode'] = vals['manual_barcode']
            elif not vals['manual_barcode'] and self.manual_barcode:
                # Revert to auto-generated barcode if manual is cleared
                book = self.book_id
                existing_count = self.search_count([('book_id', '=', book.id)])
                vals['barcode'] = f"{book.isbn}-{existing_count:03d}"
        return super(LibraryBookBarcode, self).write(vals)


class LibraryBookCategory(models.Model):
    _name = 'library.book.category'
    _description = 'Library Book Category'

    name = fields.Char(string='Name', required=True, translate=True)  # Translatable
    book_ids = fields.One2many('library.book', 'category_id', string='Books')
    book_count = fields.Integer(string='Book Count', compute='_compute_book_stats')
    available_book_count = fields.Integer(string='Available Books', compute='_compute_book_stats')
    book_names = fields.Text(string='Book Names', compute='_compute_book_stats')

    def _compute_book_stats(self):
        for category in self:
            books = self.env['library.book'].search([('category_id', '=', category.id)])
            category.book_count = len(books)
            category.available_book_count = len(books.filtered(lambda b: b.is_available))
            category.book_names = '\n'.join(books.mapped('name'))[:200]