function Form(idx, url){
    this.idx = idx;
    this.url = url;
    // Using this is just temporary for now
    this.messenger = Messenger({theme: 'flat'});
}

String.prototype.capitalize = function() {
    return this.charAt(0).toUpperCase() + this.slice(1);
}

Form.prototype.idx = null;
Form.prototype.url = null;

Form.prototype.toggle_spinning_icons = function() {
    $.each($('.indicator'), function(i, element) {
        var spinclass = this.dataset['spinclass'];
        this.dataset['spinclass'] = $(this).attr('class');
        $(this).attr('class', spinclass);
    });
}

// TODO, we call start before we start and finish before we finish, each time.
// Ideally, it should not be possible to call start twice without the first
// start having gotten to a finish already.  This might be a good place to look
// into using "promises".
//
Form.prototype.start = function() {
    // TODO -- clear all error divs before attempt this,
    // both knock their content, and hide them
    $(this.idx + " button").attr("disabled", "disable");
    this.toggle_spinning_icons();
}

Form.prototype.finish = function() {
    $(this.idx + " button").attr("disabled", null);
    this.toggle_spinning_icons();
}

Form.prototype.success = function(data) {
    var self = this;
    // cornice typically returns errors hung on error responses, but here we
    // are adding our own "caveats" list *optionally* to successful responses
    // that can explain more about what happened.
    // For instance, you might submit an update with positive karma on your own
    // update.  We'll accept the comment (success!) but add a note to the
    // response informing you that your positive karma was stripped from the
    // payload.  Here we display those caveats to users.
    caveats = data.caveats || [];  // May be undefined...
    $.each(caveats, function(i, caveat) {
        msg = self.messenger.post({
            message: caveat.description,
            type: "info"
        });
    });
    msg = self.messenger.post({
        message: "Success",
        type: "success"
    });

    // And the preview.
    $('#preview').html('');

    self.finish();
}

Form.prototype.error = function(data) {
    var self = this;
    self.finish();
    if (data.status >= 500) {
        // In case of Internal Server Error show error modal
        var msg = '';

        $.each(data.responseJSON.errors, function (i, error) {
            if (msg != '') {
                msg += '; ';
            }
            msg += error.name.capitalize() + ' : ' + error.description;
        });

        $('#alertModalDescription').text(msg);
        $('#alertModal').modal('show');
    }
    else {
        // Here is where we handle those error messages on the response by cornice.
        $.each(data.responseJSON.errors, function (i, error) {
            msg = self.messenger.post({
                message: error.name.capitalize() + ' : ' + error.description,
                type: "error",
                hideAfter: false,
                showCloseButton: true,
            });
        });
    }
}

Form.prototype.data = function() {
    var data = {};
    $(this.idx + " :input").each(function() {
        // Initialize if this is our first time through.
        if (data[this.name] === undefined) { data[this.name] = []; }
        if (this.type == 'radio' && ! this.checked) {
            // pass - don't add unchecked radio buttons to the submission
        } else if (this.type == 'checkbox' && ! this.checked) {
            // Handle series and singletons differently.
            // The checkbox lists of bugs and builds are series.
            // The single checkboxes for require_bugs, etc.. are singletons.
            if (this.dataset.singleton == 'true') {
                data[this.name].push(false);
            }
        } else {
            var value = $(this).val();
            if (value && value != "") {
                data[this.name].push(value);
            }
        }
    });

    $(this.idx + " select").each(function() {
        var value = $(this).val();
        if (value) {
            data[this.name] = value;
        } else {
            value = [];
        }
    });

    // Flatten things into scalars if we can
    $.each(data, function (key, value) {
        if (value.length == 1) { data[key] = value[0]; }
    });

    return data;
}

Form.prototype.submit = function() {
    var self = this;
    self.start();

    $.ajax(this.url, {
        method: 'POST',
        data: JSON.stringify(self.data()),
        dataType: 'json',
        contentType: 'application/json',
        success: function(data) { return self.success(data); },
        error: function(data) { return self.error(data); },
    })
}
