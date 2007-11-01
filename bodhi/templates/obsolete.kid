<div xmlns:py="http://purl.org/kid/ns#">
    <link rel="stylesheet" href="${tg.url('/static/css/flora.css')}" type="text/css" media="screen" />
    <link rel="stylesheet" href="${tg.url('/static/css/flora.dialog.css')}" type="text/css" media="screen" />
    <link rel="stylesheet" href="${tg.url('/static/css/flora.resizable.css')}" type="text/css" media="screen" />
    <script type="text/javascript" charset="utf-8" src="${tg.url('/static/js/ui.dialog.js')}"></script>
    <script type="text/javascript" charset="utf-8" src="${tg.url('/static/js/ui.resizable.js')}"></script>
    <script type="text/javascript" charset="utf-8" src="${tg.url('/static/js/ui.mouse.js')}"></script>
    <script type="text/javascript" charset="utf-8" src="${tg.url('/static/js/ui.draggable.js')}"></script>
    <script type="text/javascript" charset="utf-8" src="${tg.url('/static/js/ajax.js')}"></script>

    <span py:if="dialog">
        <div id="obsolete" title="Obsolete Updates" style="display: none">
            Please select the testing/pending updates that you would like to obsolete:
            ${dialog.display()}

            <center>
                <div id="post_data"></div>
            </center>

            <script>
                $(document).ready(function(){
                    $("#obsolete").dialog({ height: 280, width: 340 });
                    $('div.flash').hide();
                    $("#obsolete").show();
                });
            </script>
        </div>
    </span>
</div>
