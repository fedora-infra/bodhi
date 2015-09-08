var keys = [];
var konami = '38,38,40,40,37,39,37,39,66,65';
$(document).keydown(function(event) {
    keys.push(event.keyCode);
    if (keys.toString().indexOf(konami) >= 0) {
        cabbage.spin();
        keys = [];
    }
});
