odoo.define('eacta_bibliothèque.PosStyleFilters', function (require) {
    "use strict";

    var KanbanController = require('web.KanbanController');
    var KanbanView = require('web.KanbanView');
    var viewRegistry = require('web.view_registry');

    var PosStyleFilterController = KanbanController.extend({
        events: _.extend({}, KanbanController.prototype.events, {
            'click .pos-style-filter-button': '_onFilterButtonClick',
        }),

        /**
         * @override
         */
        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                // Add active class to the button that matches current domain
                self._updateActiveButton();
            });
        },

        /**
         * Handle filter button click
         */
        _onFilterButtonClick: function (ev) {
            ev.preventDefault();
            var $button = $(ev.currentTarget);
            var actionId = $button.attr('name').match(/\d+/)[0];

            // Remove active class from all buttons
            this.$('.pos-style-filter-button').removeClass('active');

            // Add active class to clicked button
            $button.addClass('active');

            // Trigger the action
            this.do_action(parseInt(actionId));
        },

        /**
         * Update active button based on current domain
         */
        _updateActiveButton: function () {
            var self = this;
            var currentDomain = this.model.get(this.handle).domain || [];

            // Check each button to see if its domain matches current domain
            this.$('.pos-style-filter-button').each(function() {
                var $button = $(this);
                var actionId = $button.attr('name').match(/\d+/)[0];

                // Fetch action domain via RPC
                self._rpc({
                    model: 'ir.actions.act_window',
                    method: 'read',
                    args: [[parseInt(actionId)], ['domain']],
                }).then(function (result) {
                    if (result && result[0]) {
                        var buttonDomain = result[0].domain || '[]';
                        buttonDomain = JSON.parse(buttonDomain.replace(/'/g, '"'));

                        // Simple domain comparison (for basic domains)
                        if (JSON.stringify(currentDomain) === JSON.stringify(buttonDomain)) {
                            $button.addClass('active');
                        }
                    }
                });
            });
        },
    });

    var PosStyleFilterKanbanView = KanbanView.extend({
        config: _.extend({}, KanbanView.prototype.config, {
            Controller: PosStyleFilterController,
        }),
    });

    // Register the view
    viewRegistry.add('library_loan_kanban', PosStyleFilterKanbanView);
});