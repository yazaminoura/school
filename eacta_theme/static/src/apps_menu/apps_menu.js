/** @odoo-module **/

import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";
import { NavBar } from "@web/webclient/navbar/navbar";

const normalize = (str) =>
    (str || "")
        .normalize("NFD")
        .replace(/[̀-ͯ]/g, "")
        .toLowerCase();

patch(NavBar.prototype, {
    setup() {
        super.setup(...arguments);
        this.nrApps = useState({ search: "" });
        let stored = null;
        try {
            stored = typeof window !== "undefined" ? localStorage.getItem("eacta_sidebar_collapsed") : null;
        } catch {
            stored = null;
        }
        this.nrSidebar = useState({ collapsed: stored === "true" });
        if (typeof window !== "undefined" && window.innerWidth >= 768 && this.nrSidebar.collapsed) {
            document.body.classList.add("o_sidebar_collapsed");
        }
        // Menu arborescent (style actaERP) : applications dépliables, filtre, élément actif
        this.nrTree = useState({ filter: "", expanded: {}, activeId: null });
        this.nrCompanyService = useService("company");
        this.nrToggleSidebar = this.nrToggleSidebar.bind(this);
        this.nrOnAppsMenuStateChanged = this.nrOnAppsMenuStateChanged.bind(this);
        this.onNavBarDropdownItemSelection = this.onNavBarDropdownItemSelection.bind(this);
    },

    async adapt() {
        if (typeof window !== "undefined" && window.innerWidth >= 768) {
            const sectionsMenu = this.appSubMenus?.el;
            if (sectionsMenu) {
                const sections = sectionsMenu.querySelectorAll(":scope > *:not(.o_menu_sections_more)");
                for (const section of sections) {
                    section.classList.remove("d-none");
                }
            }
            this.currentAppSectionsExtra = [];
            return;
        }
        return super.adapt();
    },

    nrToggleSidebar() {
        this.nrSidebar.collapsed = !this.nrSidebar.collapsed;
        if (typeof window !== "undefined") {
            try {
                localStorage.setItem("eacta_sidebar_collapsed", this.nrSidebar.collapsed ? "true" : "false");
            } catch {}
            document.body.classList.toggle("o_sidebar_collapsed", this.nrSidebar.collapsed);
        }
    },

    get apps() {
        return (this.menuService ? this.menuService.getApps() : this._apps) || [];
    },

    set apps(value) {
        this._apps = value;
    },

    get nrFilteredApps() {
        const apps = this.apps || [];
        const query = normalize(this.nrApps?.search).trim();
        if (!query) {
            return apps;
        }
        return apps.filter((app) => normalize(app.name).includes(query));
    },

    nrAppInitial(app) {
        return (app?.name || "?").trim().charAt(0).toUpperCase();
    },

    nrOnAppsMenuStateChanged(isOpen) {
        if (isOpen) {
            setTimeout(() => document.querySelector(".o_nr_apps_search input")?.focus(), 50);
        } else if (this.nrApps) {
            this.nrApps.search = "";
        }
    },

    nrOnSearchKeydown(ev) {
        if (ev.key === "Enter") {
            const [first] = this.nrFilteredApps;
            if (first) {
                ev.preventDefault();
                this.onNavBarDropdownItemSelection(first);
            }
        }
    },

    // ------------------------------------------------------------------
    // Menu arborescent de la barre latérale
    // ------------------------------------------------------------------

    /**
     * Arbre affiché : une entrée par application, avec ses lignes aplaties.
     * Une section qui a des enfants devient un titre (« EXPÉDITIONS »),
     * une section sans enfant devient un lien direct.
     */
    get nrSideTree() {
        const query = normalize(this.nrTree.filter).trim();
        const tree = [];
        for (const app of this.apps) {
            const appTree = this.menuService.getMenuAsTree(app.id);
            const appMatches = query && normalize(app.name).includes(query);
            const rows = [];
            for (const section of appTree.childrenTree || []) {
                this._nrFlatten(section, 0, rows, query && !appMatches ? query : "");
            }
            if (query && !appMatches && !rows.length) {
                continue;
            }
            tree.push({
                app,
                rows,
                expanded: query ? true : this.nrIsAppExpanded(app),
                isCurrent: this.menuService.getCurrentApp()?.id === app.id,
            });
        }
        return tree;
    },

    _nrFlatten(menu, depth, rows, query, parentMatches = false) {
        const children = menu.childrenTree || [];
        const matches = !query || parentMatches || normalize(menu.name).includes(query);
        if (children.length) {
            const childRows = [];
            for (const child of children) {
                this._nrFlatten(child, depth + 1, childRows, query, matches && !!query);
            }
            if (childRows.length) {
                rows.push({ menu, depth, isHeader: true });
                rows.push(...childRows);
            }
        } else if (matches) {
            rows.push({ menu, depth, isHeader: false });
        }
    },

    nrIsAppExpanded(app) {
        if (app.id in this.nrTree.expanded) {
            return this.nrTree.expanded[app.id];
        }
        return this.menuService.getCurrentApp()?.id === app.id;
    },

    nrOnAppClick(app) {
        if (this.nrSidebar.collapsed) {
            this.nrToggleSidebar();
            this.nrTree.expanded[app.id] = true;
            return;
        }
        const appTree = this.menuService.getMenuAsTree(app.id);
        if (!(appTree.childrenTree || []).length) {
            this.nrOnSideItemClick(app);
            return;
        }
        this.nrTree.expanded[app.id] = !this.nrIsAppExpanded(app);
    },

    nrOnSideItemClick(menu) {
        this.nrTree.activeId = menu.id;
        this.onNavBarDropdownItemSelection(menu);
    },

    nrOnLinkClick(ev, menu) {
        // Ctrl/Cmd/Maj + clic : laisser le navigateur ouvrir un nouvel onglet
        if (ev.ctrlKey || ev.metaKey || ev.shiftKey) {
            return;
        }
        ev.preventDefault();
        this.nrOnSideItemClick(menu);
    },

    nrOnFilterKeydown(ev) {
        if (ev.key === "Escape") {
            this.nrTree.filter = "";
        } else if (ev.key === "Enter") {
            const first = this.nrSideTree.flatMap((entry) => entry.rows).find((row) => !row.isHeader);
            if (first) {
                ev.preventDefault();
                this.nrOnSideItemClick(first.menu);
            }
        }
    },

    get nrUser() {
        const name = user.name || "";
        return {
            name,
            initial: name.trim().charAt(0).toUpperCase() || "?",
            company: this.nrCompanyService?.currentCompany?.name || "",
        };
    },

    nrGetAppIcon(app) {
        const name = normalize(app?.name);
        const xmlid = (app?.xmlid || "").toLowerCase();
        if (xmlid.includes("eacta_school") || name.includes("school") || name.includes("ecole")) return "fa-graduation-cap";
        if (xmlid.includes("library") || name.includes("biblioth")) return "fa-book";
        if (xmlid.includes("event") || name.includes("evenement")) return "fa-calendar";
        if (name.includes("discuss") || name.includes("discussion")) return "fa-comments-o";
        if (name.includes("factur") || name.includes("invoic") || name.includes("compta")) return "fa-file-text-o";
        if (name.includes("contact")) return "fa-address-book-o";
        if (name.includes("calendrier") || name.includes("calendar")) return "fa-calendar-o";
        if (name.includes("activit") || name.includes("to-do") || name.includes("todo")) return "fa-check-square-o";
        if (name.includes("employ")) return "fa-users";
        if (name.includes("site web") || name.includes("website")) return "fa-globe";
        if (name.includes("tableau") || name.includes("dashboard")) return "fa-th-large";
        if (name.includes("parametre") || name.includes("settings") || name.includes("theme")) return "fa-cog";
        if (name.includes("application") || name.includes("apps")) return "fa-th";
        return null;
    },

    /**
     * Icône d'une entrée du menu arborescent, d'après son nom (sans accents).
     * Les règles les plus précises passent en premier.
     */
    nrGetSideItemIcon(menu) {
        const name = normalize(menu?.name);
        const rules = [
            ["tableau de bord", "fa-th-large"], ["dashboard", "fa-th-large"],
            ["generer", "fa-magic"], ["analyse", "fa-bar-chart"], ["categorie", "fa-tags"],
            ["type", "fa-list-ul"],
            ["scanner", "fa-qrcode"], ["faire l'appel", "fa-check-square-o"], ["appel", "fa-check-square-o"],
            ["assiduite", "fa-calendar-check-o"], ["absence", "fa-calendar-check-o"],
            ["passage de fin", "fa-level-up"], ["promotion", "fa-level-up"],
            ["parent", "fa-user-plus"], ["eleve", "fa-user"], ["classe", "fa-users"],
            ["cahier de textes", "fa-book"], ["devoir", "fa-pencil"],
            ["emploi du temps", "fa-calendar"], ["creneau", "fa-clock-o"],
            ["bulletin de paie", "fa-file-text"], ["bulletins de paie", "fa-file-text"],
            ["bulletin", "fa-file-text-o"], ["deliberation", "fa-gavel"], ["examen", "fa-pencil-square-o"],
            ["note", "fa-star-o"], ["cours", "fa-book"],
            ["incident", "fa-flag"], ["sanction", "fa-gavel"], ["annonce", "fa-bullhorn"],
            ["infirmerie", "fa-medkit"], ["vaccin", "fa-eyedropper"], ["certificat", "fa-file-text-o"],
            ["effectif", "fa-cutlery"], ["menu", "fa-cutlery"], ["abonnement", "fa-id-card-o"],
            ["contrat", "fa-id-badge"], ["massar", "fa-upload"],
            ["paiement", "fa-credit-card"], ["frais", "fa-money"],
                        ["ligne", "fa-bus"], ["arret", "fa-map-marker"], ["transport", "fa-bus"],
            ["pret", "fa-exchange"], ["emprunt", "fa-exchange"], ["retour", "fa-undo"],
            ["exemplaire", "fa-barcode"], ["livre", "fa-bookmark"], ["catalogue", "fa-bookmark"],
            ["lecteur", "fa-users"], ["comptoir", "fa-desktop"],
            ["evenement", "fa-calendar"], ["inscription", "fa-id-badge"], ["autorisation", "fa-check-circle-o"],
            ["annee", "fa-calendar-o"], ["trimestre", "fa-calendar-o"], ["periode", "fa-calendar-o"],
            ["niveau", "fa-sitemap"], ["enseignant", "fa-user-circle-o"],
            ["style", "fa-paint-brush"], ["theme", "fa-paint-brush"],
            ["parametre", "fa-cog"], ["configuration", "fa-cog"], ["reglage", "fa-cog"],
        ];
        const match = rules.find(([key]) => name.includes(key));
        return match ? match[1] : "fa-circle-o";
    },

    nrGetSectionIcon(section) {
        const name = (section?.name || "").toLowerCase();
        const xmlid = (section?.xmlid || "").toLowerCase();
        if (xmlid.includes("dashboard") || name.includes("tableau de bord")) return "fa-th-large";
        if (xmlid.includes("scolarite") || name.includes("scolarité") || name.includes("élèves")) return "fa-graduation-cap";
        if (xmlid.includes("pedagogie") || name.includes("pédagogie") || name.includes("cours")) return "fa-book";
        if (xmlid.includes("finance") || name.includes("finances") || name.includes("frais")) return "fa-credit-card";
        if (xmlid.includes("reporting") || xmlid.includes("analysis") || name.includes("analyse")) return "fa-bar-chart";
        if (xmlid.includes("config") || name.includes("configuration") || name.includes("paramètres")) return "fa-cog";
        if (xmlid.includes("attendance") || name.includes("assiduité") || name.includes("absence")) return "fa-calendar-check-o";
        if (xmlid.includes("exam") || name.includes("examen")) return "fa-file-text-o";
        if (xmlid.includes("timetable") || name.includes("emploi du temps")) return "fa-clock-o";
        if (name.includes("emprunt")) return "fa-exchange";
        if (name.includes("livre") || name.includes("catalogue")) return "fa-bookmark";
        if (name.includes("lecteur")) return "fa-users";
        if (name.includes("événement") || name.includes("evenement")) return "fa-calendar";
        if (name.includes("inscription")) return "fa-id-badge";
        return "fa-folder-open-o";
    },

    nrGetSubItemIcon(item) {
        const name = (item?.name || "").toLowerCase();
        if (name.includes("élève")) return "fa-user";
        if (name.includes("classe")) return "fa-users";
        if (name.includes("assiduité") || name.includes("absence")) return "fa-calendar-check-o";
        if (name.includes("appel")) return "fa-check-circle-o";
        if (name.includes("parent")) return "fa-user-plus";
        if (name.includes("passage") || name.includes("promotion")) return "fa-level-up";
        if (name.includes("cours")) return "fa-book";
        if (name.includes("examen")) return "fa-pencil-square-o";
        if (name.includes("note")) return "fa-star-o";
        if (name.includes("emploi du temps")) return "fa-calendar";
        if (name.includes("créneau")) return "fa-clock-o";
        if (name.includes("frais")) return "fa-file-text-o";
        if (name.includes("paiement")) return "fa-credit-card";
        if (name.includes("générer")) return "fa-magic";
        if (name.includes("analyse")) return "fa-line-chart";
        if (name.includes("niveau")) return "fa-sitemap";
        if (name.includes("catégorie")) return "fa-tags";
        if (name.includes("enseignant")) return "fa-user-circle-o";
        if (name.includes("type")) return "fa-list-ul";
        return "fa-angle-right";
    },
});
