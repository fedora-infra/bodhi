var examples_loading_message = "Searching for example messages that match this filter";

var load_examples = function(page) {
    // First, destroy the more button if there is one.
    $('#more-button').remove();

    // Then, get the next page of data from the API (relative url)..
    $.ajax("ex/" + page, {
        success: examples_success,
        error: examples_error,
    });
}

var examples_success = function(data, status, jqXHR) {
    var stopping = false;
    if (data.results.length == 0) {

        // Animate some dots while we search
        $('#examples-container .lead').append('.');
        var title = $('#examples-container .lead').html();
        if (title.match('\.\.\.\.\.$') == '.....') {
            $('#examples-container .lead').html(examples_loading_message);
        }
        load_examples(data.next_page);
    } else {
        $('#examples-container .lead').html(
            "The following messages would have matched this filter");
        stopping = true;
    }

    // Put our results on the page.
    $.each(data.results, function(i, meta) {
        var content = "<li class='list-group-item example-message'>";

        if (meta.icon2 != "" && meta.icon2 != null) {
            content = content + "<img src='" + meta.icon2 + "'/>";
        }
        if (meta.icon != "" && meta.icon != null) {
            content = content + "<img src='" + meta.icon + "'/>";
        }

        if (meta.link != "" && meta.link != null) {
            content = content +
                " <a href='" + meta.link + "'>" + meta.time + "</a> ";
        } else {
            content = content + " " + meta.time + " ";
        }

        content = content + "<strong>" + meta.subtitle + "</strong> ";

        content = content + '</li>'

        $('#examples-container .list-group').append(content)
        $('#examples-container .list-group li:last-child').hide();
        $('#examples-container .list-group li:last-child').slideDown('slow');
    });

    // Tack a MOAR button on the end
    if (stopping) {
        var button = '<div id="more-button">' +
            '<button class="btn btn-default btn-lg center-block" ' +
            'onclick="javascript:load_examples(' + data.next_page + ');">' +
            '<span class="glyphicon glyphicon-cloud-download"></span>' +
            ' tap for more...' +
            '</button>' +
            '</div>';
        $('#examples-container .list-group').append(button)
        $('#examples-container .list-group div:last-child').hide();
        $('#examples-container .list-group div:last-child').slideDown('slow');
    }
}

var examples_error = function(jqXHR, status, errorThrown) {
    data = jqXHR.responseJSON;
    $('#examples-container .lead').html(data.reason);
    if (data.furthermore != undefined) {
        $('#examples-container').append('<p>' + data.furthermore + '</p>');
    }
    $('#examples-container p').addClass('text-danger');
}

$(document).ready(function() {
    // Kick it off, but only if we're on the right page.
    var container = $('#examples-container');
    if (container.length > 0) {
        $('#examples-container .lead').html(examples_loading_message);
        load_examples(1);
    }
});
