/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const HOUR_HEIGHT = 64; // px par heure

export class SchoolTimetable extends Component {
    static template = "eacta_school.Timetable";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const params = this.props.action?.params || {};
        this.state = useState({
            mode: params.mode || "class",
            recordId: params.record_id || false,
            filters: { classes: [], teachers: [], rooms: [] },
            data: null,
        });
        onWillStart(async () => {
            this.state.filters = await this.orm.call("eacta.timetable.slot", "get_timetable_filters", []);
            if (!this.state.recordId) {
                const first = this.options[0];
                this.state.recordId = first ? first.id : false;
            }
            await this.load();
        });
    }

    get options() {
        const { classes, teachers, rooms } = this.state.filters;
        return { class: classes, teacher: teachers, room: rooms }[this.state.mode] || [];
    }

    get hours() {
        const d = this.state.data;
        if (!d) {
            return [];
        }
        return Array.from({ length: d.end - d.start }, (_, i) => d.start + i);
    }

    get gridHeight() {
        return this.hours.length * HOUR_HEIGHT;
    }

    async load() {
        if (!this.state.recordId) {
            this.state.data = null;
            return;
        }
        this.state.data = await this.orm.call("eacta.timetable.slot", "get_timetable_data", [
            this.state.mode,
            this.state.recordId,
        ]);
    }

    async onModeChange(ev) {
        this.state.mode = ev.target.value;
        const first = this.options[0];
        this.state.recordId = first ? first.id : false;
        await this.load();
    }

    async onRecordChange(ev) {
        const value = ev.target.value;
        this.state.recordId = this.state.mode === "room" ? value : parseInt(value);
        await this.load();
    }

    slotsFor(day) {
        return this.state.data.slots.filter((s) => s.weekday === day);
    }

    slotStyle(slot) {
        const top = (slot.from - this.state.data.start) * HOUR_HEIGHT;
        const height = Math.max((slot.to - slot.from) * HOUR_HEIGHT - 4, 22);
        return `top: ${top}px; height: ${height}px;`;
    }

    openSlot(slotId) {
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "eacta.timetable.slot",
                res_id: slotId,
                views: [[false, "form"]],
                target: "new",
            },
            { onClose: () => this.load() }
        );
    }

    newSlot(day) {
        const context = { default_weekday: day || "0" };
        if (this.state.mode === "class") {
            context.default_class_id = this.state.recordId;
        } else if (this.state.mode === "teacher") {
            context.default_teacher_id = this.state.recordId;
        } else {
            context.default_room = this.state.recordId;
        }
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "eacta.timetable.slot",
                views: [[false, "form"]],
                target: "new",
                context,
            },
            { onClose: () => this.load() }
        );
    }

    openList() {
        this.action.doAction("eacta_school.action_eacta_timetable_slot");
    }

    async print() {
        if (this.state.mode === "class" && this.state.recordId) {
            const action = await this.orm.call("eacta.class", "action_print_timetable", [[this.state.recordId]]);
            this.action.doAction(action);
        }
    }
}

registry.category("actions").add("eacta_school.timetable", SchoolTimetable);
