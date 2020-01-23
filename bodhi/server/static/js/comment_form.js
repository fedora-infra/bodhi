// This file handles the submission of new comments to an update

$(document).ready(function() {
    var base = document.baseURI;
    var CommentsForm = function() {};
    CommentsForm.prototype = new Form("#new_comment", base + "comments/");
    CommentsForm.prototype.success = function(data) {
        Form.prototype.success.call(this, data);
        // And then issue a redirect 1 second later.
        setTimeout(function() {
            document.location.href = base + "updates/" + data.comment.update.alias;
        }, 1000);
    }

    // Wire up the submit button
    $("#submit").click(function (e) {
        var theform = new CommentsForm();
        theform.submit();
    });

    $("#preview_button").click(function(){
    update_markdown_preview($("#text").val());
    $( "#preview_button" ).addClass("active");
    $( "#edit_button" ).removeClass("active");
    $( "#text" ).hide();
    $( ".comment-preview" ).show();
  });

    $("#edit_button").click(function(){
    $( "#preview_button" ).removeClass("active");
    $( "#edit_button" ).addClass("active");
    $( "#text" ).show();
    $( ".comment-preview" ).hide();
  });

  $("input[type=radio]").change(function(){
    if ($(this).attr("value") == 1){
      $(this).parents(".list-group-item").addClass("list-group-item-success")
      $(this).parents(".list-group-item").removeClass("list-group-item-danger")
    } else if ($(this).attr("value") == -1) {
      $(this).parents(".list-group-item").removeClass("list-group-item-success")
      $(this).parents(".list-group-item").addClass("list-group-item-danger")
    } else {
      $(this).parents(".list-group-item").removeClass("list-group-item-success")
      $(this).parents(".list-group-item").removeClass("list-group-item-danger")
    }
  });
});
