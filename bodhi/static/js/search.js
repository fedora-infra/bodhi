
$(document).ready(function() {
    var updates = new Bloodhound({
        datumTokenizer: Bloodhound.tokenizers.obj.whitespace('value'),
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        remote: {
            url: 'updates/?like=%QUERY',
            filter: function(response) { return response.updates; },
        }
    });
    var users = new Bloodhound({
        datumTokenizer: Bloodhound.tokenizers.obj.whitespace('value'),
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        remote: {
            url: 'users/?like=%QUERY',
            filter: function(response) { return response.users; },
        }
    });
    var overrides = new Bloodhound({
        datumTokenizer: Bloodhound.tokenizers.obj.whitespace('value'),
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        remote: {
            url: 'overrides/?like=%QUERY',
            filter: function(response) { return response.overrides; },
        }
    });

    updates.initialize();
    users.initialize();
    overrides.initialize();

    $('#bloodhound .typeahead').typeahead({
        hint: true,
        highlight: true,
        minLength: 2,
    },
    {
        name: 'updates',
        displayKey: 'title',
        source: updates.ttAdapter(),
        templates: {
            header: '<h3 class="search">Updates</h3>',
            empty: [
                '<div class="empty-message">',
                'unable to find any updates that match the current query',
                '</div>'
            ].join('\n'),
        },
    },
    {
        name: 'users',
        displayKey: 'name',
        source: users.ttAdapter(),
        templates: {
            header: '<h3 class="search">Users</h3>',
            empty: [
                '<div class="empty-message">',
                'unable to find any users that match the current query',
                '</div>'
            ].join('\n'),
            suggestion: function(datum) {
                return '<p><img class="img-circle" src="' + datum.avatar + '">' + datum.name + '</p>';
            },
        },
    },
    {
        name: 'overrides',
        displayKey: 'nvr',
        source: overrides.ttAdapter(),
        templates: {
            header: '<h3 class="search">Buildroot Overrides</h3>',
            empty: [
                '<div class="empty-message">',
                'unable to find any overrides that match the current query',
                '</div>'
            ].join('\n'),
        },
    });

    $('#bloodhound input.typeahead').on('typeahead:selected', function (e, datum) {
        if (datum.alias != undefined) {
            window.location.href = '/updates/' + datum.alias;
        } else if (datum.title != undefined ) {
            window.location.href = '/updates/' + datum.title;
        } else if (datum.name != undefined) {
            window.location.href = '/users/' + datum.name;
        } else if (datum.nvr != undefined) {
            window.location.href = '/overrides/' + datum.nvr;
        } else {
            console.log("unhandled search result");
            console.log(datum);
        }
    });

    // Our ajaxy search is hidden by default.  Only show it if this is running
    // (and therefore if the user has javascript enabled).
    $("form#search").removeClass('hidden');
});
