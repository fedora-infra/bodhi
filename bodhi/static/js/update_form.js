
$(document).ready(function() {
    var messenger = Messenger({theme: 'flat'});

    var packages = new Bloodhound({
        datumTokenizer: Bloodhound.tokenizers.obj.whitespace('value'),
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        remote: {
            url: '/search/packages?term=%QUERY',
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
        displayKey: 'label',
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
        messenger.post({
            message: 'No candidate builds found for ' + package,
            type: 'error',
        });
    }
    var bugs_error = function(package) {
        messenger.post({
            message: 'No bugs found for ' + package,
            type: 'error',
        });
    }

    $('#packages-search input.typeahead').on('typeahead:selected', function (e, datum) {
        // Get the candidate builds
        $.ajax({
            url: '/latest_candidates',
            data: $.param({package: datum.label}),
            success: function(builds) {
                if (builds.length == 0) {return candidate_error(datum.label);}
                $.each(builds, function(i, build) {
                    $("#rhbz-checkboxes").append(
                        [
                            '<div class="checkbox">',
                            '<label>',
                            '<input type="checkbox" value="">',
                            build,
                            '</label>',
                            '</div>',
                    ].join('\n'));
                });
            },
            error: function() {candidate_error(datum.label);},
        });
        var base = 'https://apps.fedoraproject.org/packages/fcomm_connector';
        var prefix = '/bugzilla/query/query_bugs/%7B%22filters%22:%7B%22package%22:%22';
        var suffix = '%22,%22version%22:%22%22%7D,%22rows_per_page%22:5,%22start_row%22:0%7D';
        $.ajax({
            url: base + prefix + datum.label + suffix,
            success: function(data) {
                data = JSON.parse(data);
                if (data.rows.length == 0) {return bug_error(datum.label);}
                $.each(data.rows, function(i, bug) {
                    $("#bugs-checkboxes").append(
                        [
                            '<div class="checkbox">',
                            '<label>',
                            '<input type="checkbox" value="">',
                            '<a href="https://bugzilla.redhat.com/show_bug.cgi?id=' + bug.id + '">',
                            '#' + bug.id + '</a> ' + bug.description,
                            '</label>',
                            '</div>',
                    ].join('\n'));
                });
                // TODO -- tack on 'And 200 more bugs..'
            },
            error: function() {bugs_error(datum.label);},
        });
    });
});
