// This file handles all the magic that happens in the 'New Update Form'

$(document).ready(function() {
    UpdatesForm = function() {};
    UpdatesForm.prototype = new Form("#new-update-form", document.baseURI + "updates/");
    UpdatesForm.prototype.success = function(data) {
        // display caveat popups first
        Form.prototype.success.call(this, data);
        // And then issue a redirect 1 second later.
        setTimeout(function() {
            // There are two kinds of success to distinguish:
            // 1) we submitted a single update
            // 2) we submitted a multi-release update that created multiple new
            var base = document.baseURI;
            if (data.updates === undefined) {
                // Single-release update
                // Now redirect to the update display
                document.location.href = base + "updates/" + data.title;
            } else {
                // Multi-release update
                // Redirect to updates created by *me*
                document.location.href = base + "users/" + data.updates[0].user.name;
            }
        }, 1000);
    }

    var messenger = Messenger({theme: 'flat'});

    // These next couple blocks of code wire up the auto-complete search for
    // packages in the update form.  Two technologies are at play here.  The
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

    $('#packages-search .typeahead').typeahead({
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
    var bugs_error = function(package) {
        $("#bugs-checkboxes .spinner").remove();
        messenger.post({
            message: 'No bugs found for ' + package,
            type: 'error',
        });
    }

    // Callback to remove a checkbox when it is unchecked.
    // https://github.com/fedora-infra/bodhi/issues/260
    var remove_unchecked = function() {
        if (!$(this).is(":checked")) {
            $(this).parent().parent().remove();
        }
    };

    // A utility for adding another candidate build to the checkbox list of
    // candidate builds this update could include.
    // The code here is a little long because we need to additionally wire up
    // code to fire when one of those checkboxes is clicked.  (It adds
    // changelog entries to the update notes).
    var add_build_checkbox = function(nvr, idx, checked) {
        if (nvr == '' || nvr == null || nvr === undefined) return;
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
        $("#candidate-checkboxes input:first-of-type").click(remove_unchecked);

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
                    $("#notes").val( [
                            $("#notes").val(), "",
                            self.attr('data-build-nvr'), "",
                            data.rows[0].text, "",
                    ].join('\n'));
                    update_markdown_preview($("#notes").val());
                }
            })
        });
    }

    // A utility for adding another bug to the checkbox list of potential bugs
    // this update could fix.
    var add_bug_checkbox = function(idx, description, checked) {
        if (idx == '' || idx == null || idx === undefined) return;
        $("#bugs-checkboxes").prepend(
            [
                '<div class="checkbox">',
                '<label>',
                '<input name="bugs" type="checkbox" value="' + idx + '"' + (checked ? ' checked' : '') + '>',
                '<a href="https://bugzilla.redhat.com/show_bug.cgi?id=' + idx + '">',
                '#' + idx + '</a> ' + description,
                '</label>',
                '</div>',
        ].join('\n'));
        $("#bugs-checkboxes input:first-of-type").click(remove_unchecked);
    }

    // This wires up the action that happens when the user selects something
    // from the "add a package" typeahead search box.  When they do that, we
    // fire off two async js calls to get bugs and builds.  Those are then
    // added to their respective checkbox lists once they are retrieved.
    $('#packages-search input.typeahead').on('typeahead:selected', function (e, datum) {
        $("#candidate-checkboxes").prepend("<img class='spinner' src='static/img/spinner.gif'>")
        $("#bugs-checkboxes").prepend("<img class='spinner' src='static/img/spinner.gif'>")
        // Get a list of currently checked items
        var checked_bug_ids = [];
        $("#bugs-checkboxes input:checkbox:checked").each(function(){
            checked_bug_ids.push(parseInt($(this).val()));
        });
        var checked_candidate_ids = [];
        $("#candidate-checkboxes input:checkbox:checked").each(function(){
            checked_candidate_ids.push(parseInt($(this).attr('data-build-id')));
        });
        // Get the candidate builds
        $.ajax({
            url: 'latest_candidates',
            data: $.param({package: datum.name}),
            success: function(builds) {
                $("#candidate-checkboxes .spinner").remove();
                $("#candidate-checkboxes input:checkbox:not(:checked)").parents("div.checkbox").remove();
                if (builds.length == 0) {return candidate_error(datum.name);}
                $.each(builds, function(i, build) {
                    // Insert the checkbox only if this ID is not already listed
                    if ($.inArray(build.id, checked_candidate_ids) == -1) {
                        add_build_checkbox(build.nvr, build.id, false);
                    }
                });
            },
            error: function() {candidate_error(datum.name);},
        });
        var base = 'https://apps.fedoraproject.org/packages/fcomm_connector';
        var prefix = '/bugzilla/query/query_bugs/%7B%22filters%22:%7B%22package%22:%22';
        var suffix = '%22,%22version%22:%22%22%7D,%22rows_per_page%22:8,%22start_row%22:0%7D';
        $.ajax({
            url: base + prefix + datum.name + suffix,
            success: function(data) {
                $("#bugs-checkboxes .spinner").remove();
                $("#bugs-checkboxes input:checkbox:not(:checked)").parents("div.checkbox").remove();
                data = JSON.parse(data);
                if (data.rows.length == 0) {return bugs_error(datum.name);}
                $.each(data.rows, function(i, bug) {
                    // Insert the checkbox only if this ID is not already listed
                    if ($.inArray(bug.id, checked_bug_ids) == -1) {
                        add_bug_checkbox(bug.id, bug.description, false);
                    }
                });
                // TODO -- tack on 'And 200 more bugs..'
            },
            error: function() {bugs_error(datum.name);},
        });
    });

    // Rig it up so that if the user types in a custom value to the 'builds'
    // field or the 'bugs' field, those things get added to the list of
    // possibilities.
    var add_bugs = function() {
        var value = $("#bugs-adder input").val().trim();
        $.each(value.split(","), function(i, intermediary) {
            $.each(intermediary.trim().split(" "), function(j, item) {
                item = item.trim()
                if (item[0] == '#') { item = item.substring(1); }
                add_bug_checkbox(item, '', true);
            });
        });
        $("#bugs-adder input").val('');  // Clear the field
        return false;
    }
    var add_builds = function() {
        var value = $("#builds-adder input").val().trim();
        $.each(value.split(","), function(i, intermediary) {
            $.each(intermediary.trim().split(" "), function(j, item) {
                add_build_checkbox(item.trim(), false, true);
            });
        });
        $("#builds-adder input").val('');  // Clear the field
        return false;
    }

    // If you press "enter", make it count
    $("#bugs-adder input").keypress(function (e) {
        if (e.which == 13) { return add_bugs(); }
    });
    $("#builds-adder input").keypress(function (e) {
        if (e.which == 13) { return add_builds(); }
    });
    // If you "tab" away from the input, make it count.
    $("#bugs-adder input").focusout(function(e) { return add_bugs(); });
    $("#builds-adder input").focusout(function(e) { return add_builds(); });
    // Or, if you click the "+" button, make it count
    $("#bugs-adder button").click(function(e) { return add_bugs(); });
    $("#builds-adder button").click(function(e) { return add_builds(); });

    // Wire up the submit button
    $("#submit").click(function (e) {
        var theform = new UpdatesForm();
        theform.submit();
    });

    // Lastly show the main form
    $("#new-update-form").removeClass('hidden');
    // and set focus to the packages input
    $("#packages-search input.typeahead").focus();

    update_markdown_preview($("#notes").val());

});
