
$(document).ready(function() {
    var packages = new Bloodhound({
      datumTokenizer: function (datum) {
          return Bloodhound.tokenizers.whitespace(datum.value);
      },
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        remote: {
            wildcard: '%QUERY',
            url: 'packages/?search=%QUERY',
            transform: function(response) { return response.packages; },
            rateLimitWait: 600,
        }
    });
    var updates = new Bloodhound({
        datumTokenizer: Bloodhound.tokenizers.obj.whitespace('value'),
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        remote: {
            wildcard: '%QUERY',
            url: 'updates/?search=%QUERY',
            transform: function(response) { return response.updates; },
            rateLimitWait: 600,
        }
    });
    var users = new Bloodhound({
        datumTokenizer: Bloodhound.tokenizers.obj.whitespace('value'),
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        remote: {
            wildcard: '%QUERY',
            url: 'users/?search=%QUERY',
            transform: function(response) { return response.users; },
            rateLimitWait: 600,
        }
    });
    var overrides = new Bloodhound({
        datumTokenizer: Bloodhound.tokenizers.obj.whitespace('value'),
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        remote: {
            wildcard: '%QUERY',
            url: 'overrides/?search=%QUERY',
            transform: function(response) { return response.overrides; },
            rateLimitWait: 600,
        }
    });

    packages.initialize();
    updates.initialize();
    users.initialize();
    overrides.initialize();

    function resultUrl(data){
      if (data.alias != undefined) {
          return '/updates/' + data.alias;
      } else if (data.name != undefined && data.hasOwnProperty('email')) {
          return '/users/' + data.name;
      } else if (data.name != undefined) {
          return'/updates/?packages=' + encodeURIComponent(data.name);
      } else if (data.nvr != undefined) {
          return '/overrides/' + data.nvr;
      } else {
          console.log("unhandled search result");
          console.log(data);
          return '#';
      }
    }

    $('#bloodhound .typeahead').typeahead({
        hint: false,
        highlight: true,
        minLength: 2,
    },
    {
        name: 'packages',
        displayKey: 'name',
        source: packages.ttAdapter(),
        templates: {
            header: '<h3 class="search"><small>Packages</small></h3>',
            pending: [
                '<h3 class="search"><small>Packages</small></h3>',
                '<div>',
                '<i class="fa fa-spinner fa-spin fa-fw"></i>',
                '</div>'
            ].join('\n'),
            empty: [
                '<h3 class="search"><small>Packages</small></h3>',
                '<div class="empty-message text-muted">',
                'no matching packages',
                '</div>'
            ].join('\n'),
            suggestion: function(datum) {
                return '<p><a href="'+ resultUrl(datum)+'">'+datum.name+'</a></p>';
            },
        },
    },
    {
        name: 'updates',
        display: 'title',
        source: updates.ttAdapter(),
        templates: {
            header: '<h3 class="search"><small>Updates</small></h3>',
            pending: [
                '<h3 class="search"><small>Updates</small></h3>',
                '<div>',
                '<i class="fa fa-spinner fa-spin fa-fw"></i>',
                '</div>'
            ].join('\n'),
            empty: [
                '<h3 class="search"><small>Updates</small></h3>',
                '<div class="empty-message text-muted">',
                'no matching updates',
                '</div>'
            ].join('\n'),
            suggestion: function(datum) {
                return '<p><a href="'+ resultUrl(datum)+'">'+datum.title+' <span class="text-muted">'+datum.alias+'</span></a></p>';
            },
        },
    },
    {
        name: 'users',
        display: 'name',
        source: users.ttAdapter(),
        templates: {
            header: '<h3 class="search"><small>Users</small></h3>',
            pending: [
                '<h3 class="search"><small>Users</small></h3>',
                '<div>',
                '<i class="fa fa-spinner fa-spin fa-fw"></i>',
                '</div>'
            ].join('\n'),
            empty: [
                '<h3 class="search"><small>Users</small></h3>',
                '<div class="empty-message text-muted">',
                'no matching users',
                '</div>'
            ].join('\n'),
            suggestion: function(datum) {
                return '<p><a href="'+ resultUrl(datum)+'"><img class="rounded-circle" src="' + datum.avatar + '">' + datum.name + '</a></p>';
            },
        },
    },
    {
        name: 'overrides',
        display: 'nvr',
        source: overrides.ttAdapter(),
        templates: {
            header: '<h3 class="search"><small>Buildroot Overrides</small></h3>',
            pending: [
                '<h3 class="search"><small>Buildroot Overrides</small></h3>',
                '<div>',
                '<i class="fa fa-spinner fa-spin fa-fw"></i>',
                '</div>'
            ].join('\n'),
            empty: [
                '<h3 class="search"><small>Buildroot Overrides</small></h3>',
                '<div class="empty-message text-muted">',
                'no matching overrides',
                '</div>'
            ].join('\n'),
            suggestion: function(datum) {
                return '<p><a href="'+ resultUrl(datum)+'">'+datum.nvr+'</a></p>';
            },
        },
    });

    $('#bloodhound input.typeahead').on('typeahead:selected', function (e, datum) {
        window.location.href = resultUrl(datum);
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
            var value = $("form#search .tt-input").val();
            window.location.href = '/updates/?search=' + encodeURIComponent(value);
        }
    });
});
