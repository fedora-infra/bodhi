var selector = "#container";

$(document).ready(function() {
    var data = $.param({
        'delta': 1000000,  // 12 days
        'rows_per_page': 100,
        'order': 'desc',
        'meta': ['link', 'secondary_icon', 'subtitle'],
        'topic': Object.keys(handlers),
    }, true);
    $.ajax({
        url: "https://apps.fedoraproject.org/datagrepper/raw/",
        data: data,
        dataType: "jsonp",
        success: function(data) {
            hollaback(data);
        },
        error: function(data, statusCode) {
            console.log("Status code: " + statusCode);
            console.log(data);
            console.log(data.responseText);
            console.log(data.status);
        }
    });
    var hollaback = function(data) {
        $('.spinner').remove();
        var last = null;
        $.each(data.raw_messages, function(i, msg) {
            last = ellipsis(last, msg);
            handler = handlers[msg.topic];
            handler(msg);
        });
    };
});

var ellipsis = function(last, msg) {
    var time = moment(msg.timestamp.toString(), '%X');
    if (last == null) {
        return time;
    }
    four_hours = moment(last).subtract(3, 'hours');
    if (time.isBefore(four_hours)) {
        delta = last.from(time, true) + " earlier";
        $(selector).append('<div class="text-center text-muted"><i class="fa fa-ellipsis-v"></i></div>');
        $(selector).append('<div class="text-center text-muted">' + delta + '</div>');
        $(selector).append('<div class="text-center text-muted"><i class="fa fa-ellipsis-v"></i></div>');
    }
    return time
};
var avatar = function(url) {
    return "<img src='" + url + "' class='img-circle' width=32 height=32/>";
};

var request_handler = function(msg) {
    // Do the simple thing first
    simple_handler(msg);
    // But also list what updates were in the request...
    $(selector).append("<ul>");
    $.each(msg.msg.updates, function(j, update) {
        $(selector).append(
            "<li>" +
            "<a href='https://bodhi.fedoraproject.org/updates/" + update + "'>" +
            update +
            "</a>" +
            "</li>"
        );
    });
    $(selector).append("</ul>");
};

var simple_handler = function(msg) {
    var time = moment(msg.timestamp.toString(), '%X');
    var subtitle = msg.meta.subtitle;

    var cls = 'text-default';
    if (subtitle.indexOf('failed') > -1)
        cls = 'text-danger';
    else if (subtitle.indexOf('success') > -1)
        cls = 'text-success';
    else if (subtitle.indexOf('start') > -1)
        cls = 'text-muted';

    $(selector).append(
        "<p class='" + cls + "'>" +
        avatar(msg.meta.secondary_icon) + " " +
        subtitle +
        " <small>" +
        time.fromNow() + " " +
        "</small> ");
    if (msg.meta.link != null) {
        $(selector).append(
            "<strong><a href='" + msg.meta.link + "'>(details)</a></strong>");
    }
    $(selector).append("</p>");
}

handlers = {
    'org.fedoraproject.prod.bodhi.masher.start': request_handler,

    // These are maybe not interesting since they're not really from the masher
    // 'org.fedoraproject.prod.bodhi.updates.fedora.sync': simple_handler,
    // 'org.fedoraproject.prod.bodhi.updates.epel.sync': simple_handler,

    // These are noisy....
    //'org.fedoraproject.prod.bodhi.update.complete.testing': simple_handler,
    //'org.fedoraproject.prod.bodhi.update.complete.stable': simple_handler,
    //'org.fedoraproject.prod.bodhi.errata.publish': simple_handler,

    'org.fedoraproject.prod.bodhi.update.eject': simple_handler,

    // These are less noisy, but also noisy.
    //'org.fedoraproject.prod.bodhi.mashtask.sync.wait': simple_handler,
    //'org.fedoraproject.prod.bodhi.mashtask.sync.done': simple_handler,

    'org.fedoraproject.prod.bodhi.mashtask.start': simple_handler,
    'org.fedoraproject.prod.bodhi.mashtask.mashing': simple_handler,
    'org.fedoraproject.prod.bodhi.mashtask.complete': simple_handler,

};
