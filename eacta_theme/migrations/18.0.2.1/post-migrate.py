from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Renomme les styles « E-ACTA … » et applique le style NR School."""
    cr.execute("UPDATE eacta_theme_config SET name = replace(name, 'E-ACTA ', 'NR School ') WHERE name LIKE 'E-ACTA %'")
    env = api.Environment(cr, SUPERUSER_ID, {})
    preset = env.ref('eacta_theme.theme_preset_nr_school', raise_if_not_found=False)
    if preset:
        env['eacta.theme.config'].search([('id', '!=', preset.id)]).write({'is_current': False})
        preset.write({'is_current': True, 'active': True})
