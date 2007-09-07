<form xmlns:py="http://purl.org/kid/ns#"
    name="${name}"
    action="${action}"
    method="${method}"
    py:attrs="form_attrs" width="100%">

    <script type="text/javascript">
    $(document).ready(function() {
        $("#addField").click( function() {
            o = $("input[@id=form_builds_text]:eq(0)");
            o.clone().val( o.val() ).insertAfter( o.parent().parent() ).show();
            o.focus().val("");
        } );
    });
    </script>

    <div py:for="field in hidden_fields"
         py:replace="field.display(value_for(field), **params_for(field))" />

    <table border="0" cellspacing="0" cellpadding="0">
    <tr py:for="i, field in enumerate(fields)">
        <td class="title">
            <span py:if="field.label == 'Build' or i == 7">
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
