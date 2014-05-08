// Defines a cabbage object that controls animation.
function Form(idx, url){
    this.idx = idx;
    this.url = url;
    // Using this is just temporary for now
    this.messenger = Messenger({theme: 'flat'});
}

Form.prototype.idx = null;
Form.prototype.url = null;

// TODO, we call start before we start and finish before we finish, each time.
// Ideally, it should not be possible to call start twice without the first
// start having gotten to a finish already.  This might be a good place to look
// into using "promises".
//
Form.prototype.start = function() {
    var self = this;
    // TODO -- clear all error divs before attempt this,
    // both knock their content, and hide them
    cabbage.spin();
    $(this.idx + " button").attr("disabled", "disable");
}

Form.prototype.finish = function() {
    var self = this;
    cabbage.finish();
    $(this.idx + " button").attr("disabled", null);
}

Form.prototype.success = function(data) {
    var self = this;
    msg = self.messenger.post({
        message: "Success",
        type: "success"
    });
    $.ajax({
        url: self.url + "../comments/" + data.comment.id,
        dataType: "html",
        success: function(html) {
            $("ul#comments").append("<li>" + html + "</li>");
        },
        error: function(html) {
            // TODO -- handle this
            msg = self.messenger.post({
                message: "Unhandled error",
                type: "error"
            });
        }
    });
    self.finish();
}

Form.prototype.error = function(data) {
    var self = this;
    self.finish();
    $.each(data.responseJSON.errors, function (i, error) {
        if (error.name == "comment") {
            // TODO -- also insert this error into the form-wide alert div
            msg = self.messenger.post({
                message: error.description,
                type: "error"
            });
        } else {
            var selector = self.idx + " div[for=" + error.name + "]";
            $(selector + " strong").html(error.name);
            $(selector + " span").html(error.description);
            $(selector).removeClass('hidden');
        }
    });
}

Form.prototype.data = function() {
    var data = {};
    $(this.idx + " :input").each(function() {
        if (data[this.name] === undefined) { data[this.name] = []; }
        if (this.type == 'radio' && ! this.checked) {
            // pass - don't add unchecked radio buttons to the submission
        } else {
            data[this.name].push($(this).val());
        }
    });
    return data;
}

Form.prototype.submit = function() {
    var self = this;
    self.start();

    $.ajax(this.url, {
        method: 'POST',
        data: $.param(self.data(), traditional=true),
        dataType: 'json',
        success: function(data) { return self.success(data); },
        error: function(data) { return self.error(data); },
    })
}
