<form xmlns:py="http://purl.org/kid/ns#"
    name="${name}"
    action="${action}"
    method="${method}"
    py:attrs="form_attrs" width="100%">

    <link rel="stylesheet" href="${tg.url('/static/css/jquery.tooltip.css')}" />
    <script src="${tg.url('/static/js/jquery.dimensions.js')}" type="text/javascript"></script>
    <script src="${tg.url('/static/js/jquery.tooltip.js')}" type="text/javascript"></script>
    <script src="${tg.url('/static/js/chili-1.7.pack.js')}" type="text/javascript"></script>
    <script src="${tg.url('/static/js/jquery.bgiframe.js')}" type="text/javascript"></script>

    <script type="text/javascript">
    $(document).ready(function() {
        $("#addField").click( function() {
            o = $("input[@id=form_builds_text]:eq(0)");
            o.clone().val(" "+o.val()).insertAfter(o.parent().parent()).show();
            o.focus().val("");
        } );

        $("#form_builds_text").attr("title", "Update Builds - A space or comma delimited list of name-version-release builds");
        $("#form_builds_text").Tooltip({
            extraClass: "pretty fancy", showBody:   " - ", left: 5, top: -15,
            fixPNG: true, opacity: 1
        });
        $("#form_notes").Tooltip({
            extraClass: "pretty fancy", showBody:   " - ", left: 5, top: -15,
            fixPNG: true, opacity: 1
        });
        $("#form_bugs").Tooltip({
                extraClass: "pretty fancy", showBody:   " - ", left: 5,
                top: -15, fixPNG: true, opacity: 1
        });
        $("#form_cves").Tooltip({
                extraClass: "pretty fancy", showBody:   " - ", left: 5,
                top: -15, fixPNG: true, opacity: 1
        });
        $("#form_close_bugs").Tooltip({
                extraClass: "pretty fancy", showBody:   " - ", left: 5,
                top: -15, fixPNG: true, opacity: 1
        });
        $("#form_inheritance").Tooltip({
                extraClass: "pretty fancy", showBody: " - ", left: 5,
                top: -15, fixPNG: true,
        });
        $("#form_suggest_reboot").Tooltip({
                extraClass: "pretty fancy", showBody: " - ", left: 5,
                top: -15, fixPNG: true,
        });
        $("#form_autokarma").Tooltip({
                extraClass: "pretty fancy", showBody: " - ", left: 5,
                top: -15, fixPNG: true,
        });
        $("#form_stable_karma").Tooltip({
                extraClass: "pretty fancy", showBody: " - ", left: 5,
                top: -15, fixPNG: true,
        });
        $("#form_unstable_karma").Tooltip({
                extraClass: "pretty fancy", showBody: " - ", left: 5,
                top: -15, fixPNG: true,
        });
    });
    </script>

    <div py:for="field in hidden_fields"
         py:replace="field.display(value_for(field), **params_for(field))" />

    <table border="0" cellspacing="0" cellpadding="0">
    <tr py:for="i, field in enumerate(fields)">
        <td class="title">
            <span py:if="i == 6">
                <?python continue ?>
            </span>
            <label class="fieldlabel"
                   for="${field.field_id}"
                   py:content="field.label"/>
        </td>
        <td class="value">
            <font color="red">
                <span py:if="error_for(field)"
                      class="fielderror"
                      py:content="error_for(field)" />
            </font>
            <span py:replace="field.display(value_for(field), **params_for(field))"/>
            <span py:if="i == 4">
              <label for="form_close_bugs">${display_field_for('close_bugs')} Close bugs when update is stable</label>
            </span>
            <span py:if="field.help_text"
                  class="fieldhelp"
                  py:content="field.help_text" />
        </td>
    </tr>
    <tr>
        <td class="title" />
        <td class="value" py:content="submit.display(submit_text)" />
    </tr>
    </table>

</form>
