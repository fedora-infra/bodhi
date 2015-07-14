// This file handles all the magic that happens in the 'New Override Form'

$(document).ready(function() {
    OverridesForm = function() {};
    OverridesForm.prototype = new Form("#new-override-form", "/overrides/");
    OverridesForm.prototype.success = function(data) {
        Form.prototype.success.call(this, data);

        // Now redirect to the override display page
        document.location.href = "/overrides/" + data.build.nvr;
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
    // candidates in the override form.  Two technologies are at play here.  The
    // first is 'bloodhound' which is a suggestion engine.  Its suggestions are
    // then fed to 'typeahead.js' which is responsible for presenting and
    // acting on the suggestions.
    var url = 'latest_candidates?package=';

    var candidates = new Bloodhound({
        datumTokenizer: Bloodhound.tokenizers.obj.whitespace('value'),
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        remote: {
            url: url + '%QUERY',
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

    // Lastly, hide our warning and show the main form
    $("#js-warning").addClass('hidden');
    $("#new-override-form").removeClass('hidden');
});
