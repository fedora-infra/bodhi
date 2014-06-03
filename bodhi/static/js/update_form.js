
$(document).ready(function() {
    var messenger = Messenger({theme: 'flat'});

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


    var add_build_checkbox = function(nvr, idx, checked) {
        $("#candidate-checkboxes").prepend(
            [
                '<div class="checkbox">',
                '<label>',
                '<input data-build-nvr="' + nvr + '"' +
                    (idx ? '" data-build-id="' + idx + '" ' : ' ') +
                    'type="checkbox" value=""' + (checked ? ' checked' : '') + '>',
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
    var add_bug_checkbox = function(idx, description, checked) {
        $("#bugs-checkboxes").prepend(
            [
                '<div class="checkbox">',
                '<label>',
                '<input type="checkbox" value=""' + (checked ? ' checked' : '') + '>',
                '<a href="https://bugzilla.redhat.com/show_bug.cgi?id=' + idx + '">',
                '#' + idx + '</a> ' + description,
                '</label>',
                '</div>',
        ].join('\n'));
    }

    $('#packages-search input.typeahead').on('typeahead:selected', function (e, datum) {
        $("#candidate-checkboxes").prepend("<img class='spinner' src='/static/img/spinner.gif'>")
        $("#bugs-checkboxes").prepend("<img class='spinner' src='/static/img/spinner.gif'>")
        // Get the candidate builds
        $.ajax({
            url: '/latest_candidates',
            data: $.param({package: datum.name}),
            success: function(builds) {
                $("#candidate-checkboxes .spinner").remove();
                if (builds.length == 0) {return candidate_error(datum.name);}
                $.each(builds, function(i, build) {
                    add_build_checkbox(build.nvr, build.id, false);
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
                data = JSON.parse(data);
                if (data.rows.length == 0) {return bugs_error(datum.name);}
                $.each(data.rows, function(i, bug) {
                    add_bug_checkbox(bug.id, bug.description, false);
                });
                // TODO -- tack on 'And 200 more bugs..'
            },
            error: function() {bugs_error(datum.name);},
        });
    });
    $("#bugs-adder").keypress(function (e) {
        if (e.which == 13) {
            var value = $(this).val().trim();
            if (value[0] == '#') { value = value.substring(1); }
            add_bug_checkbox(value, '', true);
            return false;
        }
    });
    $("#builds-adder").keypress(function (e) {
        if (e.which == 13) {
            var value = $(this).val().trim();
            add_build_checkbox(value, false, true);
            return false;
        }
    });


});
