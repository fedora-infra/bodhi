var delay = (function(){
  var timer = 0;
  return function(callback, ms){
    clearTimeout (timer);
    timer = setTimeout(callback, ms);
  };
})();

var update_markdown_preview = function(text) {
    delay(function() {
        $("#preview").html("<h3><small>Loading</small></h3>");
        $.ajax({
            url: "markdown",
            data: $.param({text: text}),
            dataType: 'json',
            success: function(data) {
                $("#preview").html(data.html);
            },
            error: function(e1, e2, e3) {
                $("#preview").html("<h3><small>Error loading preview</small></h3>");
            }
        });
    }, 500);
}

$(document).ready(function() {
    // Kick it off, but only if we're on the right page.
    var container = $('#examples-container');
    if (container.length > 0) {
        $('#examples-container .lead').html(examples_loading_message);
        load_examples(1);
    }

    $('#text, #notes').keyup(function() {
        update_markdown_preview($(this).val());
    });

    // Attach bootstrap tooltips to everything.
    $('[data-toggle="tooltip"]').tooltip();
    $('[data-toggle="popover"]').popover();


    // Make the rows on the comment form change color on click.
    $('.table td > input').click(function() {
        var td = $(this).parent();
        td.parent().removeClass('danger');
        td.parent().removeClass('success');
        td.parent().addClass(td.attr('data-class'));
    });

    $('.searchbar .typeahead').blur(function(){
        $('.searchbar').slideUp();
    });

    $('#search-toggle').click(function(){
      if ($('.searchbar').is(":hidden")){
        $('.searchbar').slideDown();
        $('.searchbar .typeahead').focus();
      }
    });
});
