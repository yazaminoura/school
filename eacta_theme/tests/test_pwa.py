# -*- coding: utf-8 -*-
import json
from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestSchoolPWA(common.HttpCase):

    def test_01_pwa_manifest(self):
        """Vérifie la route du Web App Manifest PWA et ses champs obligatoires."""
        res = self.url_open('/school/manifest.webmanifest')
        self.assertEqual(res.status_code, 200)
        self.assertIn('application/manifest+json', res.headers.get('Content-Type', ''))

        data = json.loads(res.text)
        self.assertEqual(data.get('short_name'), 'NR School')
        self.assertEqual(data.get('theme_color'), '#8E1B3A')
        self.assertEqual(data.get('display'), 'standalone')
        self.assertTrue(len(data.get('icons', [])) >= 2)

    def test_02_service_worker(self):
        """Vérifie le Service Worker pour le cache et le support hors-ligne."""
        res = self.url_open('/school/sw.js')
        self.assertEqual(res.status_code, 200)
        self.assertIn('application/javascript', res.headers.get('Content-Type', ''))
        self.assertIn('CACHE_NAME', res.text)
        self.assertIn('/school/offline', res.text)

    def test_03_offline_page(self):
        """Vérifie le chargement de la page de secours hors-ligne."""
        res = self.url_open('/school/offline')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Connexion Interrompue', res.text)
        self.assertIn('offline-card', res.text)

    def test_04_portal_mobile_elements(self):
        """Vérifie la présence du lien manifest, de la barre de navigation mobile et de la bannière d'installation."""
        res = self.url_open('/my')
        self.assertEqual(res.status_code, 200)
        self.assertIn('/school/manifest.webmanifest', res.text)
        self.assertIn('nrschool-mobile-nav', res.text)
        self.assertIn('nrschool-pwa-install-banner', res.text)
        self.assertIn('nrschool-pwa-ios-modal', res.text)
