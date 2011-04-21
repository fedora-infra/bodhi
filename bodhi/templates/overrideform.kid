<form xmlns:py="http://purl.org/kid/ns#"
    name="${name}"
    action="${action}"
    method="${method}"
    py:attrs="form_attrs" width="100%">

    <h2>Buildroot Override Form</h2>

    <table border="0" cellspacing="0" cellpadding="0">
    <tr py:for="i, field in enumerate(fields)">
        <td class="title">
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

    <script type="text/javascript">
    $(document).ready(function() {
        $("#addField").click( function() {
            o = $("input[@id=form_builds_text]:eq(0)");
            o.clone().val(" "+o.val()).insertAfter(o.parent().parent()).show();
            o.focus().val("");
        } );
    });
    </script>
</form>
