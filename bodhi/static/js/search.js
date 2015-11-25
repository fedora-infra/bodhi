
$(document).ready(function() {
    var packages = new Bloodhound({
        datumTokenizer: Bloodhound.tokenizers.obj.whitespace('value'),
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        remote: {
            url: 'packages/?like=%QUERY',
            filter: function(response) { return response.packages; },
        }
    });
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

    packages.initialize();
    updates.initialize();
    users.initialize();
    overrides.initialize();

    $('#bloodhound .typeahead').typeahead({
        hint: true,
        highlight: true,
        minLength: 2,
    },
    {
        name: 'packages',
        displayKey: 'name',
        source: packages.ttAdapter(),
        templates: {
            header: '<h3 class="search"><small>Packages</small></h3>',
            empty: [
                '<div class="empty-message text-muted">',
                'no matching packages',
                '</div>'
            ].join('\n'),
        },
    },
    {
        name: 'updates',
        displayKey: 'title',
        source: updates.ttAdapter(),
        templates: {
            header: '<h3 class="search"><small>Updates</small></h3>',
            empty: [
                '<div class="empty-message text-muted">',
                'no matching updates',
                '</div>'
            ].join('\n'),
        },
    },
    {
        name: 'users',
        displayKey: 'name',
        source: users.ttAdapter(),
        templates: {
            header: '<h3 class="search"><small>Users</small></h3>',
            empty: [
                '<div class="empty-message text-muted">',
                'no matching users',
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
            header: '<h3 class="search"><small>Buildroot Overrides</small></h3>',
            empty: [
                '<div class="empty-message text-muted">',
                'no matching overrides',
                '</div>'
            ].join('\n'),
        },
    });

    $('#bloodhound input.typeahead').on('typeahead:selected', function (e, datum) {
        if (datum.alias != undefined) {
            window.location.href = '/updates/' + datum.alias;
        } else if (datum.title != undefined ) {
            window.location.href = '/updates/' + datum.title;
        } else if (datum.hasOwnProperty('stack')) {
            window.location.href = '/updates/?packages=' + datum.name;
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

    // If people want to just skip our search suggestions and press
    // "enter", then we'll assume (perhaps incorrectly) that they are
    // looking for a package.. and we'll take them right to the cornice
    // service for that.   https://github.com/fedora-infra/bodhi/issues/229
    $("form#search .tt-input").keypress(function(e) {
        if (e.which == 13) {
            cabbage.spin();
            var value = $("form#search .tt-input").val();
            window.location.href = '/updates/?packages=' + value;
        }
    });
});
