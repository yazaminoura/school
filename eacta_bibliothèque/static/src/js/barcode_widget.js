odoo.define('eacta_bibliothèque.BarcodeWidget', function (require) {
    "use strict";

    var fieldRegistry = require('web.field_registry');
    var Many2ManyTags = require('web.Many2ManyTags');

    var BarcodeMany2ManyTags = Many2ManyTags.extend({
        _tagRenderer: function (tag) {
            // Display the barcode value instead of the display_name
            var $tag = $('<span>', {
                class: 'o_tag badge badge-secondary mr-1',
                text: tag.data.barcode || tag.data.display_name || tag.data.name
            });

            if (!this.isReadonly) {
                $tag.append($('<span>', {
                    class: 'o_delete',
                    'data-id': tag.id,
                    text: ' ×'
                }));
            }
            return $tag;
        }
    });

    fieldRegistry.add('barcode_many2many_tags', BarcodeMany2ManyTags);
    return BarcodeMany2ManyTags;
});