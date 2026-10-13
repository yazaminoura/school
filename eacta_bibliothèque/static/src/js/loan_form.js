odoo.define('eacta_bibliothèque.LoanForm', function (require) {
    "use strict";

    var FormController = require('web.FormController');
    var FormView = require('web.FormView');
    var viewRegistry = require('web.view_registry');

    var LoanFormController = FormController.extend({
        /**
         * @override
         */
        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                // Initial toggle
                self._toggleReturnFields();
                // Listen to changes in the returned field
                self._onChangeReturned = self._onChangeReturned.bind(self);
                self.$el.on('change', 'input[name="returned"]', self._onChangeReturned);
            });
        },

        _onChangeReturned: function () {
            this._toggleReturnFields();
        },

        _toggleReturnFields: function () {
            var returned = this.$('input[name="returned"]:checked').val() === 'true';
            this.$('.o_return_fields').toggle(returned);

            // Also update readonly status of returned_copies_count
            var returnedCopiesField = this.$('input[name="returned_copies_count"]');
            if (returnedCopiesField.length) {
                returnedCopiesField.prop('readonly', !returned);
            }
        },

        /**
         * @override
         */
        destroy: function () {
            this.$el.off('change', 'input[name="returned"]', this._onChangeReturned);
            this._super.apply(this, arguments);
        },
    });

    var LoanFormView = FormView.extend({
        config: _.extend({}, FormView.prototype.config, {
            Controller: LoanFormController,
        }),
    });

    viewRegistry.add('library_loan_form', LoanFormView);
});