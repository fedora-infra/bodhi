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
                document.location.href = base + "updates/" + data.alias;
            } else {
                // Multi-release update
                // Redirect to updates created by *me*
                document.location.href = base + "users/" + data.updates[0].user.name;
            }
        }, 1000);
    }

    var messenger = Messenger({theme: 'flat'});

    // function to load the list of bug options for the bug chooser.
    function loadBugs(packagename) {
        // generate products list for the URL from settings.bz_products (defined globally in master.html)
        var products_string = "";
        for (var p in settings.bz_products){
            products_string = products_string+'&product='+encodeURIComponent(settings.bz_products[p]);
        }
        return function(callback){
            $.ajax({
                url: settings.bz_server_rest+'bug?bug_status=__open__&component='+packagename+products_string+'&include_fields=summary,status,id,product,component,version',
                type: 'GET',
                dataType: 'jsonp',
                error: function() {
                    callback();
                },
                success: function(res) {
                    callback(res.bugs);
                }
            });
        }
    }

    var $bugs_search_selectize = $('#bugs-search').selectize( {
        create: function(input, callback){
            $("#bugs-card .selectize-control").addClass("loading")
            $.ajax({
                url: settings.bz_server_rest+'bug?id=' + encodeURIComponent(input),
                type: 'GET',
                dataType: 'jsonp',
                error: function() {
                    callback();
                },
                success: function(data) {
                    if (data.bugs.length != 1) {
                        messenger.post({
                            message: 'Cannot find data for bug #' + input + '. Either the bug is private or doesn\'t exist.',
                            type: 'error',
                        });
                        $("#bugs-card .selectize-control").removeClass("loading")
                        callback();
                    } else {
                        // Check Bug product
                        var product = data.bugs[0].product;
                        if (settings.bz_products.indexOf(product) == -1) {
                            messenger.post({
                                message: 'Bug #' + data.bugs[0].id + ' doesn\'t seem to refer to a product that Bodhi manages updates for.\nAre you sure you want to reference it in this update? Bodhi will not be able to operate on this bug!',
                                type: 'error',
                            });
                        }
                        // Alert user if bug is already closed
                        if (data.bugs[0].status == "CLOSED") {
                            messenger.post({
                                message: 'Bug #' + data.bugs[0].id + ' is already in CLOSED state.\nAre you sure you want to reference it in this update?',
                                type: 'error',
                            });
                        }
                        callback({'id': data.bugs[0].id, 'summary': data.bugs[0].summary})
                    }
                    $("#bugs-card .selectize-control").removeClass("loading")
                }
            });
        },
        valueField: 'id',
        labelField: 'id',
        searchField: ['id', 'summary', 'component'],
        createFilter: "^[0-9]+$",
        plugins: ['remove_button','restore_on_backspace'],
        onInitialize: function(){
            // make sure the placeholder shows when items already exist when page loads
            $('#bugs-search-selectized').attr("placeholder", "search and add bugs");
        },
        onBlur: function(){
            $('#bugs-search-selectized').attr("placeholder", $bugs_search_selectize.settings.placeholder);
        },
        onFocus: function(){
            $('#bugs-search-selectized').attr("placeholder", "");
        },
        render: {
            item: function(item, escape) {
                return '<div class="w-100 border-bottom m-0 py-1 pl-3">' +
                '   <span class="font-weight-bold" title="bug description">BZ#' + escape(item.id) + '</span>' +
                '   <span class="name" title="bug description">' + escape(item.summary) + '</span>' +
                '</div>';
            },
            option: function(item, escape) {
                return '<div class="w-100 border-bottom m-0 py-1 pl-3">' +
                '<div>' +
                '   <span class="font-weight-bold" title="bug description">BZ#' + escape(item.id) + '</span>' +
                '   <span class="name" title="bug description">' + escape(item.summary) + '</span>' +
                '</div>'+
                '<div>' +
                '   <span class="badge badge-light border">' + escape(item.component[0]) + '</span>' +
                '   <span class="badge badge-light border">' + escape(item.product) + ' '+escape(item.version[0])+'</span>' +
                '</div>'+
                '</div>';
            },
        },
    });
    $bugs_search_selectize = $bugs_search_selectize[0].selectize;

    var buildssearchterm = "";
    var $builds_search_selectize = $('#builds-search').selectize({
        valueField: 'nvr',
        labelField: 'nvr',
        searchField: ['nvr', 'tag_name', 'owner_name'],
        preload: true,
        plugins: ['remove_button','restore_on_backspace'],
        render: {
            option: function(item, escape) {
                return '<div class="w-100 border-bottom px-1">' +
                '   <h6 class="font-weight-bold mb-0">' + escape(item.nvr) + '</h6>' +
                '   <span class="badge badge-light border"><i class="fa fa-tag"></i> '+escape(item.release_name)+'</span> '+
                '   <span class="badge badge-light border"><i class="fa fa-user"></i> '+escape(item.owner_name)+'</span> '+
                '</div>';
            },
            item: function(item, escape) {
                return '<div class="w-100 border-bottom m-0 py-1 pl-3">' +
                       '   <span class="name">' + escape(item.nvr) + '</span>' +
                       '   <span class="badge badge-light border float-right">' + escape(item.release_name) + '</span>' +
                       '</div>';
            },
        },
        onItemAdd: function(value, item){
            $builds_search_selectize.setTextboxValue(buildssearchterm)
            $builds_search_selectize.refreshOptions(true)
            $builds_search_selectize.updatePlaceholder()

            // when adding a new build, pull the bugs into the bugs chooser options
            $bugs_search_selectize.load(loadBugs(this.options[value].package_name))
        },
        onType: function(searchterm){
            buildssearchterm = searchterm;
        },
        onBlur: function(){
            // make sure the placeholder reappears when focus is lost
            $('#builds-search-selectized').attr("placeholder", $builds_search_selectize.settings.placeholder);
        },
        onInitialize: function(){
            // make sure the placeholder shows when items already exist when page loads
            $('#builds-search-selectized').attr("placeholder", "search and add builds");

            // preload bugs from builds that exist when the page loads (i.e. when editing an existing update)
            for (var b in this.options) {
                if (this.options.hasOwnProperty(b)) {
                    $bugs_search_selectize.load(loadBugs(this.options[b].package_name))
                }

            }
            
        },
        onFocus: function(){
            // make sure the placeholder disappears when focused
            $('#builds-search-selectized').attr("placeholder", "");
        },
        load: function(query, callback) {
            $.ajax({
                url: '/latest_candidates?prefix=' + encodeURIComponent(query),
                type: 'GET',
                error: function() {
                    callback();
                },
                success: function(res) {
                    callback(res);
                }
            });
        }
    });

    $builds_search_selectize = $builds_search_selectize[0].selectize;

    $('#updatetypes').selectize();
    $('#severity').selectize();
    $('#suggest').selectize();
    $('#requirements').selectize({
        plugins: ['remove_button','restore_on_backspace'],
        delimiter: ' ',
        persist: false,
        create: function(input) {
            return {
                value: input,
                text: input
            }
        }
    });



    // Wire up the submit button
    $("#submit").click(function (e) {
        var theform = new UpdatesForm();
        theform.submit();
    });

    // Lastly show the main form
    $("#new-update-form").removeClass('hidden');

    update_markdown_preview($("#notes").val());

    var validate_severity = function() {
        var type = $("input[name=type]:checked").val();
        var severity = $("input[name=severity]:checked").val();

        if (type == 'security') {
            $("input[name=severity][value=unspecified]").attr('disabled', 'disabled');
        } else {
            $("input[name=severity][value=unspecified]").removeAttr('disabled')
        }
    }

    $("input[name=type]").on('change', validate_severity);
    $("input[name=severity]").on('change', validate_severity);
});
