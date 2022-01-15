// @license magnet:?xt=urn:btih:d3d9a9a6595521f9666a5e94cc830dab83b65699&dn=expat.txt Expat

$(document).ready(function() {
    $.typeahead({
        input: '.bodhi-searchbar-input',
        minLength: 2,
        dynamic: true,
        delay: 600,
        group: {
            template: function (item) {
                if (item.group == "overrides") {
                    return "<h3>Buildroot Overrides</h3>";
                } else {
                    return "<h3>" + item.group + "</h3>";
                }
            }
        },
        maxItem: 20,
        maxItemPerGroup: 5,
        asyncResult: true,
        emptyTemplate: 'No result for "{{query}}"',
        dropdownFilter: true,
        source: {
            packages: {
                display: 'name',
                ajax: {
                    url: 'packages/',
                    timeout: 10000,
                    data: {
                        search: '{{query}}'
                    },
                    path: 'packages'
                },
                template: '{{name}}',
                href: function (item) {
                    return 'updates/?packages=' + encodeURIComponent(item.name)
                }
            },
            updates: {
                display: ['title', 'alias'],
                ajax: {
                    url: 'updates/',
                    timeout: 10000,
                    data: {
                        search: '{{query}}'
                    },
                    path: 'updates'
                },
                template: '{{title}} <span class="text-muted">{{alias}}</span>',
                href: 'updates/{{alias}}'
            },
            users: {
                display: 'name',
                ajax: {
                    url: 'users/',
                    timeout: 10000,
                    data: {
                        search: '{{query}}'
                    },
                    path: 'users'
                },
                template: '<img class="rounded-circle mr-2" src="{{avatar}}">{{name}}',
                href: function (item) {
                    return 'users/' + encodeURIComponent(item.name)
                }
            },
            overrides: {
                display: 'nvr',
                ajax: {
                    url: 'overrides/',
                    timeout: 10000,
                    data: {
                        search: '{{query}}'
                    },
                    path: 'overrides'
                },
                template: '{{nvr}}',
                href: 'overrides/{{nvr}}'
            }
        },
        callback: {
            onSubmit: function (node, form, item, event) {
                    event.preventDefault();
                    window.location.href = '/updates/?search=' + encodeURIComponent(node.val());
                },
            onCancel: function (node, event) {
                $("#bodhi-searchbar .typeahead__list").remove();
            }
        }
    });

    $(".bodhi-searchbar-input").focus(function() {
        if ($(this).val() != '') {
            $("#bodhi-searchbar .typeahead__list").attr("style", "display: block !important");
        }
    });

    $(document).click(function(event) { 
        var target = $(event.target);
        if(!target.closest('#bodhi-searchbar').length && $('#bodhi-searchbar .typeahead__list').is(":visible")) {
            $('#bodhi-searchbar .typeahead__list').hide();
        }        
    });
});
// @license-end
