// Defines a cabbage object that controls animation.
function Cabbage(){}

Cabbage.prototype.spinning = false;
Cabbage.prototype.degrees = 0;
Cabbage.prototype.interval_id = null;
Cabbage.prototype.frequency = 50;
Cabbage.prototype.finish_time = 400;  // Finish up in 1 second

Cabbage.prototype.spin = function() {
    var self = this;
    self.degrees = self.degrees % 360
    self.stop();
    self.interval_id = setInterval(function() {
        self.degrees = self.degrees + 2;
        $("#ghost-cabbage").css({transform: "rotate(" + self.degrees + "deg)"});
    }, self.frequency);

    $("html,body").css('cursor', 'wait !important');
}

Cabbage.prototype.stop = function() {
    var self = this;
    if (self.interval_id != null) { clearInterval(self.interval_id); }
}

Cabbage.prototype.finish = function() {
    var self = this;

    // Stop the initial rotation.
    self.stop();

    // Normalize ourselves
    self.degrees = self.degrees % 360;

    // In self.finish_time ms, finish landing at 0/360
    distance = 360 - self.degrees;
    num_steps = self.finish_time / self.frequency;
    delta = distance / num_steps;

    // Set up a self-stopping rotation to finish out self.finish_time.
    self.interval_id = setInterval(function() {
        self.degrees = self.degrees + delta;
        if (self.degrees >= 360) {
            self.degrees = 0;
            self.stop();
            $("#ghost-cabbage").css({transform: "rotate(" + self.degrees + "deg)"});
        } else {
            $("#ghost-cabbage").css({transform: "rotate(" + self.degrees + "deg)"});
        }
    }, self.frequency);

    $("html,body").css('cursor', 'default');
}
