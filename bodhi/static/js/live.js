$(document).ready(function() {
  WebSocketSetup(1);
});

function popup(data) {
  msg = Messenger({theme: 'flat'}).post({
    message: "<a href='" + data.meta.link + "'>" + data.meta.subtitle + "</a>",
  });
  // Furthermore, throw it on the newsfeed if its on the page
  if (window.prepend_newsfeed_card != undefined) { prepend_newsfeed_card(data.meta); }
}

function error(jqXHR, status, error) {
  console.log("Error getting hit error with this");
  console.log(jqXHR);
  console.log(status);
  console.log(error);
}

function WebSocketSetup(attempts) {
  if ( attempts > 3 ) { return; }

  if ("WebSocket" in window) {
    // Let us open a web socket
    var socket_url = "wss://hub.fedoraproject.org:9939";
    //var socket_url = "wss://209.132.181.16:9939";
    var ws = new WebSocket(socket_url);
    ws.onopen = function(e) {
      // Web Socket is connected, send data using send()
      console.log("ws connected to " + socket_url);
      ws.send(JSON.stringify({
        topic: '__topic_subscribe__',
        body: 'org.fedoraproject.prod.bodhi.*'
      }));
    };
    ws.onmessage = function (evt) {
      function get_metadata() {
        var data = JSON.parse(evt.data).body;
        var params = $.param({
          'id': data['msg_id'],
          'meta': ['subtitle', 'link', 'secondary_icon', 'icon', 'date'],
        }, traditional=true);
        $.ajax({
          url: "https://apps.fedoraproject.org/datagrepper/id/",
          dataType: 'jsonp',
          data: params,
          success: popup,
          error: error,
        });
      }
      setTimeout(get_metadata, 750);
    };
    ws.onclose = function(e){ws=null;};
    ws.onerror = function(e){ws=null;WebSocketSetup(attempts + 1);};
  }
}
