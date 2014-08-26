// This file handles all the magic that happens in the 'New Stack Form'

$(document).ready(function() {
    StackForm = function() {};
    StackForm.prototype = new Form("#new-stack-form", "/stacks/");
    StackForm.prototype.success = function(data) {
        Form.prototype.success.call(this, data);

        // Now redirect to the update display
        document.location.href = "/stacks/" + data.stack.name;
    }

    var messenger = Messenger({theme: 'flat'});

    // These next couple blocks of code wire up the auto-complete search for
    // packages in the stack form.  Two technologies are at play here.  The
    // first is 'bloodhound' which is a suggestion engine.  Its suggestions are
    // then fed to 'typeahead.js' which is responsible for presenting and
    // acting on the suggestions.
    //
    // For the search here, we query the fedora-packages webapp.
    var base = 'https://apps.fedoraproject.org/packages/fcomm_connector';
    var prefix = '/xapian/query/search_packages/%7B%22filters%22:%7B%22search%22:%22'
    var suffix = '%22%7D,%22rows_per_page%22:10,%22start_row%22:0%7D'

    var packages = new Bloodhound({
        datumTokenizer: Bloodhound.tokenizers.obj.whitespace('value'),
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        remote: {
            url: base + prefix + '%QUERY' + suffix,
            filter: function (response) {
                return $.map(response.rows, function(row) {
                    return {'name': $('<p>' + row.name + '</p>').text()}
                });
            },
        }
    });
    packages.initialize();

    $('#builds-adder').typeahead({
        hint: true,
        highlight: true,
        minLength: 1,
    },
    {
        name: 'packages',
        displayKey: 'name',
        source: packages.ttAdapter(),
        templates: {
            empty: [
                '<div class="empty-message">',
                'unable to find any packages that match the current query',
                '</div>'
            ].join('\n'),
        },
    });

    // candidate_error and bug_error are just two handy utilities for reporting
    // errors when stuff in the code blocks below this goes wrong.
    var candidate_error = function(package) {
        $("#candidate-checkboxes .spinner").remove();
        messenger.post({
            message: 'No candidate builds found for ' + package,
            type: 'error',
        });
    }
    //var bugs_error = function(package) {
    //    $("#bugs-checkboxes .spinner").remove();
    //    messenger.post({
    //        message: 'No bugs found for ' + package,
    //        type: 'error',
    //    });
    //}

    // A utility for adding another candidate build to the checkbox list of
    // candidate builds this update could include.
    // The code here is a little long because we need to additionally wire up
    // code to fire when one of those checkboxes is clicked.  (It adds
    // changelog entries to the update notes).
    var add_build_checkbox = function(nvr, idx, checked) {
        $("#candidate-checkboxes").prepend(
            [
                '<div class="checkbox">',
                '<label>',
                '<input name="builds" data-build-nvr="' + nvr + '"' +
                    (idx ? '" data-build-id="' + idx + '" ' : ' ') +
                    'type="checkbox" value="' + nvr + '"' + (checked ? ' checked' : '') + '>',
                nvr,
                '</label>',
                '</div>',
        ].join('\n'));

        $("#candidate-checkboxes .checkbox:first-child input").click(function() {
            var self = $(this);
            if (! self.is(':checked')) { return; }
            if (self.attr('data-build-id') == null) { return; }

            var base = 'https://apps.fedoraproject.org/packages/fcomm_connector';
            var prefix = '/koji/query/query_changelogs/%7B%22filters%22:%7B%22build_id%22:%22';
            var suffix = '%22,%22version%22:%22%22%7D,%22rows_per_page%22:8,%22start_row%22:0%7D';

            $.ajax({
                url: base + prefix + self.attr('data-build-id') + suffix,
                success: function(data) {
                    data = JSON.parse(data);
                    if (data.rows.length == 0) {console.log('error');}
                    $("#description").val( [
                            $("#description").val(), "",
                            self.attr('data-build-nvr'), "",
                            data.rows[0].text, "",
                    ].join('\n'));
                    update_markdown_preview($("#description").val());
                }
            })
        });
    }

        //});
    });

    $("#builds-adder").keypress(function (e) {
        if (e.which == 13) {
            var value = $(this).val().trim();
            add_build_checkbox(value, false, true);
            $('.typeahead').typeahead('close');
            $(this).val('');
            return false;
        }
    });

    // Wire up the submit button
    $("#submit").click(function (e) {
        var theform = new StackForm();
        theform.submit();
    });

    // Lastly, hide our warning and show the main form
    $("#js-warning").addClass('hidden');
    $("#new-stack-form").removeClass('hidden');
});
