<div>
    <link rel="stylesheet" href="${tg.url('/static/css/flora.css')}" type="text/css" media="screen" />
    <link rel="stylesheet" href="${tg.url('/static/css/flora.dialog.css')}" type="text/css" media="screen" />
    <link rel="stylesheet" href="${tg.url('/static/css/flora.resizable.css')}" type="text/css" media="screen" />
    <script type="text/javascript" charset="utf-8" src="${tg.url('/static/js/ui.dialog.js')}"></script>
    <script type="text/javascript" charset="utf-8" src="${tg.url('/static/js/ui.resizable.js')}"></script>
    <script type="text/javascript" charset="utf-8" src="${tg.url('/static/js/ui.mouse.js')}"></script>
    <script type="text/javascript" charset="utf-8" src="${tg.url('/static/js/ui.draggable.js')}"></script>
    <script type="text/javascript" charset="utf-8" src="${tg.url('/static/js/ajax.js')}"></script>

    <script>
    $(document).ready(function(){
        $("#obsolete").dialog({ height: 250 });
        $("#obsolete").show();
    });
    </script>

    <div id="obsolete" title="Obsolete Updates" style="display: none">
        Please select the testing/pending updates that you would like to obsolete:
        ${dialog.display()}
        <div id="post_data"></div>
    </div>

</div>
