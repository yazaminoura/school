# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request, Response


class SchoolPWAController(http.Controller):

    @http.route(['/school/manifest.webmanifest', '/manifest.webmanifest', '/manifest.json'], type='http', auth='none', cors='*')
    def pwa_manifest(self, **kw):
        """Fournit le fichier manifest PWA officiel de NR School."""
        manifest = {
            "name": "NR School - Espace Scolaire & Parental",
            "short_name": "NR School",
            "description": "Portail mobile officiel de gestion scolaire, vie scolaire et suivi parental NR School",
            "start_url": "/my",
            "scope": "/",
            "display": "standalone",
            "background_color": "#FFFFFF",
            "theme_color": "#8E1B3A",
            "orientation": "portrait",
            "lang": "fr-FR",
            "categories": ["education", "productivity"],
            "icons": [
                {
                    "src": "/eacta_theme/static/src/img/nr_school_icon_192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/eacta_theme/static/src/img/nr_school_icon_512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable"
                }
            ],
            "shortcuts": [
                {
                    "name": "Espace Scolaire",
                    "short_name": "Scolarité",
                    "description": "Accéder aux profils et bulletins de vos enfants",
                    "url": "/my/school",
                    "icons": [{"src": "/eacta_theme/static/src/img/nr_school_icon_192.png", "sizes": "192x192"}]
                },
                {
                    "name": "Mon Compte",
                    "short_name": "Profil",
                    "description": "Gérer vos coordonnées et votre sécurité",
                    "url": "/my",
                    "icons": [{"src": "/eacta_theme/static/src/img/nr_school_icon_192.png", "sizes": "192x192"}]
                }
            ]
        }
        return Response(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            headers=[
                ('Content-Type', 'application/manifest+json; charset=utf-8'),
                ('Cache-Control', 'public, max-age=3600'),
            ]
        )

    @http.route(['/school/sw.js', '/sw.js'], type='http', auth='none', cors='*')
    def pwa_service_worker(self, **kw):
        """Fournit le Service Worker pour la mise en cache et le support hors-ligne."""
        sw_code = """/* NR School Service Worker - PWA v1.0.0 */
const CACHE_NAME = 'nrschool-pwa-v1.0.0';
const STATIC_ASSETS = [
  '/eacta_theme/static/src/img/nr_school_icon_192.png',
  '/eacta_theme/static/src/img/nr_school_icon_512.png',
  '/eacta_theme/static/src/img/favicon.ico',
  '/school/offline'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  
  // Ignore non-GET or cross-origin requests
  if (req.method !== 'GET' || !req.url.startsWith(self.location.origin)) {
    return;
  }

  // Handle navigation requests (HTML pages) -> Network first, fallback to offline page
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(() => {
        return caches.match('/school/offline') || caches.match(req);
      })
    );
    return;
  }

  // Handle static assets (images, fonts, stylesheets) -> Stale-while-revalidate
  if (req.destination === 'image' || req.destination === 'style' || req.destination === 'font') {
    event.respondWith(
      caches.match(req).then((cachedResponse) => {
        const fetchPromise = fetch(req).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const responseToCache = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(req, responseToCache);
            });
          }
          return networkResponse;
        }).catch(() => cachedResponse);
        return cachedResponse || fetchPromise;
      })
    );
    return;
  }

  // Default fetch
  event.respondWith(fetch(req));
});
"""
        return Response(
            sw_code,
            headers=[
                ('Content-Type', 'application/javascript; charset=utf-8'),
                ('Service-Worker-Allowed', '/'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
            ]
        )

    @http.route(['/school/offline'], type='http', auth='public', website=True)
    def pwa_offline_page(self, **kw):
        """Page d'attente hors-ligne stylisée avec la charte NR School."""
        return request.render('eacta_theme.portal_pwa_offline')
