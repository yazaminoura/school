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

    get maxCycleAbsences() {
        if (!this.state.data.cycle_absences || !this.state.data.cycle_absences.length) {
            return 1;
        }
        return Math.max(1, ...this.state.data.cycle_absences.map((c) => c.absences));
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

    openFeesOverdue() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Frais de scolarité en retard",
            res_model: "eacta.student.fee",
            views: [[false, "list"], [false, "form"]],
            domain: [["is_overdue", "=", true]],
        });
    }

    openStrugglingStudents() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Élèves en difficulté (Moyenne < 10)",
            res_model: "eacta.student",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: [["grade_count", ">", 0], ["average", "<", 10.0]],
        });
    }

    openHonorStudents() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Tableau d'honneur (Moyenne ≥ 14)",
            res_model: "eacta.student",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: [["average", ">=", 14.0]],
        });
    }
}

registry.category("actions").add("eacta_school.dashboard", SchoolDashboard);
