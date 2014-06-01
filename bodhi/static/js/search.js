
$(document).ready(function() {
    var updates = new Bloodhound({
        datumTokenizer: Bloodhound.tokenizers.obj.whitespace('value'),
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        remote: {
            url: '/updates/?like=%QUERY',
            filter: function(response) { return response.updates; },
        }
    });
    var users = new Bloodhound({
        datumTokenizer: Bloodhound.tokenizers.obj.whitespace('value'),
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        remote: {
            url: '/users/?like=%QUERY',
            filter: function(response) { return response.users; },
        }
    });

    updates.initialize();
    users.initialize();

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
        },
    });

    $('input.typeahead').on('typeahead:selected', function (e, datum) {
        if (datum.alias != undefined) {
            window.location.href = '/updates/' + datum.alias;
        } else if (datum.title != undefined ) {
            window.location.href = '/updates/' + datum.title;
        } else if (datum.name != undefined) {
            window.location.href = '/users/' + datum.name;
        } else {
            console.log("unhandled search result");
            console.log(datum);
        }
    });

    // Our ajaxy search is hidden by default.  Only show it if this is running
    // (and therefore if the user has javascript enabled).
    $("form#search").removeClass('hidden');
});
