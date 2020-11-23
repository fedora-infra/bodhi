// This file handles all the magic that happens in the 'New Override Form'

$(document).ready(function() {
    var OverridesForm = function() {};
    OverridesForm.prototype = new Form("#new-override-form", "/overrides/");
    OverridesForm.prototype.success = function(data) {
        Form.prototype.success.call(this, data);

        setTimeout(function() {
            // There are two kinds of success to distinguish:
            // 1) we submitted a single buildroot override
            // 2) we submitted multiple NVRs that created multiple new overrides
            var base = document.baseURI;
            if (data.overrides === undefined) {
                // Single override
                // Now redirect to the override display
                document.location.href = base + "overrides/" + data.build.nvr;
            } else {
                // Multi-NVR override.
                // Redirect to overrides created by *me*
                document.location.href = base + "users/" + data.overrides[0].submitter.name;
            }
        }, 1000);
    };

    OverridesForm.prototype.expire = function() {
        var self = this;
        self.start();

        var formdata = self.data();
        formdata['expired'] = true;

        $.ajax(this.url, {
            method: 'POST',
            data: JSON.stringify(formdata),
            dataType: 'json',
            contentType: 'application/json',
            success: function(data) { return self.success(data); },
            error: function(data) { return self.error(data); },
        });
    };

    // These next couple blocks of code wire up the auto-complete search for
    // builds in the override form.

    $.typeahead({
        input: '#nvr',
        minLength: 2,
        delay: 600,
        maxItem: 20,
        dynamic: true,
        emptyTemplate: 'No result for "{{query}}"',
        source: {
            builds: {
                display: 'nvr',
                ajax: {
                    url: 'latest_candidates',
                    timeout: 10000,
                    data: {
                        testing: true,
                        prefix: '{{query}}',
                    },
                    path: '',
                },
                template: '<h6 class="font-weight-bold mb-0">{{nvr}}</h6>' +
                    '   <span class="badge badge-light border"><i class="fa fa-tag"></i>{{release_name}}</span> ' +
                    '   <span class="badge badge-light border"><i class="fa fa-user"></i> {{owner_name}}</span> ',
                templateValue: '{{nvr}}',
            }
        },
        callback: {
            onSubmit: function (node, form, item, event) {
                    event.preventDefault();
                },
            onCancel: function (node, event) {
                $("#new-override-form .typeahead__list").remove();
            }
        }
    });

    // Wire up the submit button
    $("#submit").click(function (e) {
        var theform = new OverridesForm();
        theform.submit();
    });

    $("#expire").click(function() {
        var theform = new OverridesForm();
        theform.expire();
    });

    // Lastly show the main form
    $("#new-override-form").removeClass('hidden');
});
