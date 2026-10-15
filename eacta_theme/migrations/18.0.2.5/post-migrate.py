from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """S'assure que le style par défaut est bien appliqué et que les assets sont à jour."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Theme = env['eacta.theme.config'].with_context(active_test=False)
    if not Theme.search_count([('is_current', '=', True)]):
        preset = env.ref('eacta_theme.theme_preset_nr_school', raise_if_not_found=False) or Theme.search([], limit=1)
        if preset:
            preset.write({'is_current': True, 'active': True})
