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
            // Laisse le menu s'afficher puis place le curseur dans la recherche
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
});
