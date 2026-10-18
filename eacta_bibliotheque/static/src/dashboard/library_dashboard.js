/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class LibraryDashboard extends Component {
    static template = "eacta_bibliotheque.LibraryDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, loading: true });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("library.loan", "get_library_dashboard_data", []);
        this.state.loading = false;
    }

    get kpis() {
        return this.state.data.kpis;
    }

    get maxCategory() {
        return Math.max(1, ...this.state.data.categories.map((c) => c.copies));
    }

    pct(value, total) {
        return total ? Math.round((100 * value) / total) : 0;
    }

    money(value) {
        return `${(value || 0).toFixed(2)} ${this.kpis.currency}`;
    }

    dueLabel(days) {
        if (days <= 0) {
            return "Aujourd'hui";
        }
        return days === 1 ? "Demain" : `Dans ${days} j`;
    }

    open(xmlId) {
        this.action.doAction(xmlId);
    }

    openRecord(resModel, resId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: resModel,
            res_id: resId,
            views: [[false, "form"]],
        });
    }

    async returnLoan(loanId) {
        await this.orm.call("library.loan", "action_return_book", [[loanId]]);
        await this.load();
    }
}

registry.category("actions").add("eacta_bibliotheque.dashboard", LibraryDashboard);
