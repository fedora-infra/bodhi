
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

    $('#packages-search input.typeahead').on('typeahead:selected', function (e, datum) {
        // Get the candidate builds
        console.log(datum);
        $.ajax({
            url: '/latest_candidates',
            data: $.param({package: datum.label}),
            success: function(builds) {
                if (builds.length == 0) {return candidate_error(datum.label);}
                alert(builds);
            },
            error: function() {candidate_error(datum.label);},
        });
    });
});
