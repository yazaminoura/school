from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Renomme les styles « E-ACTA … », met à jour les couleurs des presets et applique le style NR School."""
    cr.execute("UPDATE eacta_theme_config SET name = replace(name, 'E-ACTA ', 'NR School ') WHERE name LIKE 'E-ACTA %'")
    env = api.Environment(cr, SUPERUSER_ID, {})
    preset = env.ref('eacta_theme.theme_preset_nr_school', raise_if_not_found=False)
    if preset:
        # Assure les couleurs non-bleues officielles (Vert Académie & Or)
        preset.write({
            'name': 'NR School (Vert & Or)',
            'primary_color': '#0B6E4F',
            'secondary_color': '#E9A23B',
            'accent_color': '#E76F51',
            'ink_color': '#06392A',
            'is_current': True,
            'active': True,
        })
        env['eacta.theme.config'].search([('id', '!=', preset.id)]).write({'is_current': False})
