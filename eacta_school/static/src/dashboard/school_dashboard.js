/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class SchoolDashboard extends Component {
    static template = "eacta_school.SchoolDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, loading: true });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("eacta.student", "get_school_dashboard_data", []);
        this.state.loading = false;
    }

    get kpis() {
        return this.state.data.kpis;
    }

    get maxBucket() {
        return Math.max(1, ...this.state.data.distribution.map((b) => b.count));
    }

    get genderTotal() {
        const g = this.state.data.gender;
        return g.male + g.female + g.other;
    }

    pct(value, total) {
        return total ? Math.round((100 * value) / total) : 0;
    }

    scoreClass(value) {
        if (value >= 14) {
            return "o_eacta_score o_eacta_score_high";
        }
        return value < 10 ? "o_eacta_score o_eacta_score_low" : "o_eacta_score";
    }

    daysLabel(days) {
        if (days === 0) {
            return "Aujourd'hui";
        }
        return days === 1 ? "Demain" : `Dans ${days} j`;
    }

    openList(resModel, name, domain = [], context = {}, viewTypes = ["kanban", "list", "form"]) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: resModel,
            views: viewTypes.map((v) => [false, v]),
            domain,
            context,
        });
    }

    openRecord(resModel, resId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: resModel,
            res_id: resId,
            views: [[false, "form"]],
        });
    }

    openStudents(state) {
        const domain = state ? [["state", "=", state]] : [];
        this.openList("eacta.student", "Élèves", domain);
    }

    openAction(xmlId) {
        this.action.doAction(xmlId);
    }
}

registry.category("actions").add("eacta_school.dashboard", SchoolDashboard);
