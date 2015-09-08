var prepend_newsfeed_card = function(msg) {
    // This is a utility used first at page load to render each message from
    // the datagrepper history.  It is then used again later by the websocket
    // connection to render new events as they stream in.
    if (msg.secondary_icon === undefined || msg.secondary_icon == '') {
        msg.secondary_icon = msg.icon;
    }

    var card = '<div class="message-card">';
    card = card + '<img class="img-circle" src="' +
        msg.secondary_icon + '"></img>' + '<p>';
    if (msg.link != undefined && msg.link != '') {
        card = card + '<a href="' + msg.link + '">'
    }
    card = card + msg.subtitle;
    if (msg.link != undefined && msg.link != '') {
        card = card + '</a>';
    }
    card = card + '</p><div class="datetime">' + msg.date + '</div>' +
        '</div>';
    $("#datagrepper-widget").prepend(card);
}


var generate_newsfeed = function(url, badge_ids) {
    $('.onlyjs').css('visibility', 'visible');
    $('.onlyjs').css('display', 'block');

    $('.hidejs').css('visibility', 'hidden');
    $('.hidejs').css('display', 'none');

    $('.rowjs').addClass('row');

    $('.sidepaneljs').addClass('sidepanel');

    for (i = 0; i <= 12; i++) {
        $('.remove-cols').removeClass('col-md-' + i);
        $('.remove-cols').removeClass('col-md-offset-' + i);
    }

    for (i = 0; i <= 12; i++)
        $('.js-md-' + i).addClass('col-md-' + i);

    messages = {};
    $.when(
        // Gather bodhi events
        $.ajax(url + '/raw', {
            data: $.param({
                category: 'bodhi',
                grouped: true,
                delta: 1209600, // two weeks in seconds (this makes it faster)
            }),
            dataType: 'jsonp',
            success: function(data) { messages.bodhi = data.raw_messages; },
            error: function(e1, e2, e3) {
                console.log(e1);
                console.log(e2);
            }
        }),
        // Gather badge events and limit them to bodhi badges
        $.ajax(url + '/raw', {
            data: $.param({
                topic: [
                    'org.fedoraproject.prod.fedbadges.badge.award',
                    'org.fedoraproject.stg.fedbadges.badge.award',
                ],
                meta: ['subtitle', 'link', 'icon', 'date'],
                delta: 1209600, // two weeks in seconds (this makes it faster)
            }, true),
            dataType: 'jsonp',
            success: function(data) {
                messages.badges = $.map(
                    $.grep(
                        data.raw_messages,
                        function(msg) {
                            var idx = msg.msg.badge.badge_id
                            return $.inArray(idx, badge_ids) != -1;
                        }
                    ),
                    function (msg) {
                        var item = msg.meta;
                        item.timestamp = msg.timestamp;
                        item.secondary_icon = msg.meta.icon;
                        return item;
                    });
            },
            error: function(e1, e2, e3) {
                console.log(e1);
                console.log(e2);
            }
        })
    ).then(function() {
        var comparator = function(a, b) {
            if (a.timestamp > b.timestamp) return 1;
            if (a.timestamp < b.timestamp) return -1;
            return 0;
        }
        messages = $.merge(messages.bodhi, messages.badges).sort(comparator);
        $("#loader").hide();
        $.each(messages, function(i, msg) { prepend_newsfeed_card(msg); });
    })
};
