/** @odoo-module **/

import { useState } from "@odoo/owl";
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
        const stored = typeof window !== "undefined" ? localStorage.getItem("eacta_sidebar_collapsed") : null;
        this.nrSidebar = useState({ collapsed: stored === "true" });
        if (typeof window !== "undefined" && window.innerWidth >= 768 && this.nrSidebar.collapsed) {
            document.body.classList.add("o_sidebar_collapsed");
        }
    },

    adapt() {
        if (typeof window !== "undefined" && window.innerWidth >= 768) {
            const sectionsMenu = this.appSubMenus.el;
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
            localStorage.setItem("eacta_sidebar_collapsed", this.nrSidebar.collapsed ? "true" : "false");
            document.body.classList.toggle("o_sidebar_collapsed", this.nrSidebar.collapsed);
        }
    },

    get nrFilteredApps() {
        const query = normalize(this.nrApps.search).trim();
        if (!query) {
            return this.apps;
        }
        return this.apps.filter((app) => normalize(app.name).includes(query));
    },

    nrAppInitial(app) {
        return (app.name || "?").trim().charAt(0).toUpperCase();
    },

    nrOnAppsMenuStateChanged(isOpen) {
        if (isOpen) {
            setTimeout(() => document.querySelector(".o_nr_apps_search input")?.focus(), 50);
        } else {
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
