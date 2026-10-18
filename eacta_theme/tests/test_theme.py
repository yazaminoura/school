from odoo.exceptions import ValidationError
from odoo.tests import common, tagged
from ..models.theme_config import PALETTES


@tagged('post_install', '-at_install')
class TestThemeConfig(common.TransactionCase):

    def test_01_active_config_singleton_and_defaults(self):
        """Vérifie la récupération de la configuration active et les valeurs par défaut."""
        config = self.env['eacta.theme.config']._get_current()
        self.assertTrue(config)
        self.assertTrue(config.primary_color)
        self.assertTrue(config.secondary_color)
        self.assertEqual(config.navbar_style, 'gradient')

    def test_02_apply_palette_and_reset(self):
        """Vérifie l'application d'une palette prédéfinie et la réinitialisation aux valeurs d'origine."""
        config = self.env['eacta.theme.config']._get_current()
        p_emerald = PALETTES['emerald']
        config.write({
            'color_scheme': 'emerald',
            'primary_color': p_emerald[0],
            'secondary_color': p_emerald[1],
            'accent_color': p_emerald[2],
            'ink_color': p_emerald[3],
        })
        self.assertEqual(config.primary_color.upper(), '#059669')
        self.assertEqual(config.secondary_color.upper(), '#10B981')

        # Réinitialisation
        config.action_reset_defaults()
        self.assertEqual(config.primary_color.upper(), '#8E1B3A')

    def test_03_color_hex_validation(self):
        """Vérifie le contrôle strict de format hexadécimal des couleurs."""
        config = self.env['eacta.theme.config']._get_current()
        with self.assertRaises(ValidationError):
            config.write({'primary_color': 'invalid-color'})

        with self.assertRaises(ValidationError):
            config.write({'secondary_color': '#12345'})  # 5 chars instead of 6

        # Couleur valide
        config.write({'primary_color': '#1A2B3C'})
        self.assertEqual(config.primary_color, '#1A2B3C')

    def test_04_css_generation(self):
        """Vérifie que la feuille de style dynamique CSS génère bien les variables racine."""
        css = self.env['eacta.theme.config']._get_theme_css()
        self.assertIn(':root', css)
        self.assertIn('--eacta-primary:', css)
        self.assertIn('--eacta-secondary:', css)
        self.assertIn('--eacta-card-radius:', css)
