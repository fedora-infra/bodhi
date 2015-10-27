// This file handles all the magic that happens in the 'New Stack Form'

$(document).ready(function() {
    StackForm = function() {};
    StackForm.prototype = new Form("#new-stack-form", document.baseURI + "stacks/");
    StackForm.prototype.success = function(data) {
        Form.prototype.success.call(this, data);

        // Now redirect to the stack display
        document.location.href = document.baseURI + "stacks/" + data.stack.name;
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
                '<input name="packages" data-package-name="' + nvr + '"' +
                    (idx ? '" data-package-id="' + idx + '" ' : ' ') +
                    'type="checkbox" value="' + nvr + '"' + (checked ? ' checked' : '') + '>',
                nvr,
                '</label>',
                '</div>',
        ].join('\n'));

    }

    // This wires up the action that happens when the user selects something
    // from the "add a package" typeahead search box.
    $('#builds-adder').on('typeahead:selected', function (e, datum) {
        add_build_checkbox(datum.name, false, true);
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

    // Wire up the delete button
    $("#delete").click(function (e) {
      $.ajax({
        url: '/updates/stacks/' + $('#stack-name input').val(),
        type: 'DELETE',
        success: function(result) {
            document.location.href = "/updates/stacks/";
        }
      });
    });

    // Lastly show the main form
    $("#new-stack-form").removeClass('hidden');
});
