/** @odoo-module **/

document.addEventListener('DOMContentLoaded', () => {
    // -------------------------------------------------------------
    // 1. Enregistrement du Service Worker
    // -------------------------------------------------------------
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/school/sw.js', { scope: '/' })
                .then((reg) => {
                    console.log('✅ [NR School PWA] Service Worker actif. Scope:', reg.scope);
                })
                .catch((err) => {
                    console.warn('⚠️ [NR School PWA] Échec enregistrement Service Worker:', err);
                });
        });
    }

    // -------------------------------------------------------------
    // 2. Bannière d'installation PWA (Android / Chrome / Edge)
    // -------------------------------------------------------------
    let deferredPrompt = null;
    const installBanner = document.getElementById('nrschool-pwa-install-banner');
    const installBtn = document.getElementById('nrschool-pwa-install-btn');
    const dismissBtn = document.getElementById('nrschool-pwa-dismiss-btn');
    const iosInstallModal = document.getElementById('nrschool-pwa-ios-modal');

    // Vérifier si l'utilisateur a ignoré récemment la bannière (7 jours)
    const isDismissedRecently = () => {
        const lastDismissed = localStorage.getItem('nrschool_pwa_dismissed');
        if (!lastDismissed) return false;
        const days = (Date.now() - parseInt(lastDismissed, 10)) / (1000 * 60 * 60 * 24);
        return days < 7;
    };

    // Détection iOS Safari
    const isIos = () => {
        const ua = window.navigator.userAgent.toLowerCase();
        return /iphone|ipad|ipod/.test(ua);
    };

    const isInStandaloneMode = () => {
        return ('standalone' in window.navigator && window.navigator.standalone) ||
               window.matchMedia('(display-mode: standalone)').matches;
    };

    // Événement standard PWA (Android, Windows, macOS, Chrome, Edge)
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;

        if (installBanner && !isDismissedRecently() && !isInStandaloneMode()) {
            installBanner.classList.remove('d-none');
            setTimeout(() => {
                installBanner.classList.add('show');
            }, 300);
        }
    });

    if (installBtn) {
        installBtn.addEventListener('click', async () => {
            if (deferredPrompt) {
                deferredPrompt.prompt();
                const { outcome } = await deferredPrompt.userChoice;
                if (outcome === 'accepted') {
                    console.log('🎉 [NR School PWA] Installation acceptée par l\'utilisateur.');
                    if (installBanner) installBanner.classList.remove('show');
                }
                deferredPrompt = null;
            } else if (isIos() && !isInStandaloneMode()) {
                // Afficher le guide d'installation iOS
                const bsModal = window.bootstrap && window.bootstrap.Modal;
                if (bsModal && iosInstallModal) {
                    new bsModal(iosInstallModal).show();
                } else {
                    alert("Pour installer NR School sur votre iPhone / iPad :\n1. Appuyez sur l'icône de partage [⎋] en bas de Safari.\n2. Faites défiler et choisissez 'Sur l'écran d'accueil' 📲.");
                }
            }
        });
    }

    if (dismissBtn) {
        dismissBtn.addEventListener('click', () => {
            if (installBanner) {
                installBanner.classList.remove('show');
                setTimeout(() => installBanner.classList.add('d-none'), 300);
            }
            localStorage.setItem('nrschool_pwa_dismissed', Date.now().toString());
        });
    }

    // -------------------------------------------------------------
    // 3. Barre de Navigation Mobile Inférieure : Détection de l'onglet actif
    // -------------------------------------------------------------
    const currentPath = window.location.pathname;
    const navItems = document.querySelectorAll('.nrschool-mobile-nav-item');

    navItems.forEach((item) => {
        const href = item.getAttribute('href');
        if (!href) return;

        // Correspondance exacte ou préfixe de route
        if (href === '/my' && (currentPath === '/my' || currentPath === '/my/')) {
            item.classList.add('active');
        } else if (href !== '/my' && currentPath.startsWith(href)) {
            item.classList.add('active');
        }
    });
});
