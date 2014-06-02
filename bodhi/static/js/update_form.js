
$(document).ready(function() {
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

    $('#packages-search input.typeahead').on('typeahead:selected', function (e, datum) {
        console.log(datum);
    });
});
