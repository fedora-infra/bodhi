<form xmlns:py="http://purl.org/kid/ns#"
    name="${name}"
    action="${action}"
    method="${method}"
    py:attrs="form_attrs" width="100%">

    <script type="text/javascript">
    $(document).ready(function() {
        $("#addField").click( function() {
            o = $("input[@id=form_build_text]:eq(0)");
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
            <span py:if="field.label != 'Builds'">
                <label class="fieldlabel"
                       for="${field.field_id}"
                       py:content="field.label"/>
            </span>
        </td>
        <td class="value">
            <span py:replace="field.display(value_for(field), **params_for(field))"/>
            <span py:if="error_for(field)"
                  class="fielderror"
                  py:content="error_for(field)" />
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

    <!--
    <table cellpadding="0" cellspacing="0">
        <tr>
            <td class="title">
                Package(s):
            </td>
            <td class="value">
                ${display_field_for('build')}
            </td>
        </tr>
        <tr>
            <td class="title"></td>
            <td class="value" style="padding-left: 8px">
                <div id="newfield" style="display: none">
                    ${display_field_for('builds')}
                </div>
            </td>
        </tr>
        <tr>
            <td class="title">Release:</td>
            <td class="value">${display_field_for('release')}</td>
        </tr>
        <tr>
            <td class="title">Type:</td>
            <td class="value">${display_field_for('type')}</td>
        </tr>
        <tr>
            <td class="title">Bugs:</td>
            <td class="value">${display_field_for('bugs')}${display_field_for('close_bugs')}</td>
        </tr>
        <tr>
            <td class="title"><a href="http://cve.mitre.org">CVEs</a>:</td>
            <td class="value">${display_field_for('cves')}</td>
        </tr>
        <tr>
            <td class="title">Notes:</td>
            <td class="value">${display_field_for('notes')}</td>
        </tr>
        <tr>
            <td class="title"/>
            <td class="value">${display_field_for('submit')}</td>
        </tr>
    </table>
    -->
</form>
