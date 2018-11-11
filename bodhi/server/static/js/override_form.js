// This file handles all the magic that happens in the 'New Override Form'

$(document).ready(function() {
    OverridesForm = function() {};
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
    // builds in the override form.  Two technologies are at play here.  The
    // first is 'bloodhound' which is a suggestion engine.  Its suggestions are
    // then fed to 'typeahead.js' which is responsible for presenting and
    // acting on the suggestions.
    var url = 'latest_candidates?testing=true&package=';

    var candidates = new Bloodhound({
        datumTokenizer: Bloodhound.tokenizers.obj.whitespace('value'),
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        remote: {
            url: url + '%QUERY',
            rateLimitWait: 600,
        }
    });
    candidates.initialize();

    $('#candidates-search .typeahead').typeahead({
        hint: true,
        highlight: true,
        minLength: 1,
    },
    {
        name: 'candidates',
        displayKey: 'nvr',
        source: candidates.ttAdapter(),
    });

    // This wires up the action that happens when the user selects something
    // from the "add a candidate" typeahead search box.
    $('#candidates-search input.typeahead').on('typeahead:selected', function (e, datum) {
        $("#nvr").val(datum.nvr);
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
