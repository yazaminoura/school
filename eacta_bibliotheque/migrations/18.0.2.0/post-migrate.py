from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Recalcule les statuts (jamais mis à jour avant 2.0) et numérote les anciens emprunts."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Loan = env['library.loan'].with_context(active_test=False)
    Copy = env['library.book.barcode'].with_context(active_test=False)
    Book = env['library.book'].with_context(active_test=False)
    Borrower = env['library.borrower'].with_context(active_test=False)

    loans = Loan.search([])
    for field in ('state', 'is_overdue', 'was_overdue', 'complete_return', 'fine_amount', 'name', 'borrower_name'):
        env.add_to_compute(Loan._fields[field], loans)
    copies = Copy.search([])
    for field in ('state', 'is_available', 'current_loan_id'):
        env.add_to_compute(Copy._fields[field], copies)
    books = Book.search([])
    for field in ('total_quantity', 'available_quantity', 'on_loan_quantity', 'is_available', 'status'):
        env.add_to_compute(Book._fields[field], books)
    borrowers = Borrower.search([])
    for field in ('active_loans_count', 'overdue_loans_count', 'total_loans_count', 'fine_due'):
        env.add_to_compute(Borrower._fields[field], borrowers)
    env.flush_all()

    for loan in loans.filtered(lambda l: not l.reference or l.reference == '/').sorted('id'):
        loan.reference = env['ir.sequence'].next_by_code('library.loan')
