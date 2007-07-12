<form xmlns:py="http://purl.org/kid/ns#"
    name="${name}"
    action="${tg.url('/comment')}"
    method="${method}"
    py:attrs="form_attrs" width="100%"
    onsubmit="$('bodhi-logo').style.display = 'none'; $('wait').style.display='block'">

    <div py:for="field in hidden_fields"
         py:replace="field.display(value_for(field), **params_for(field))" />

    <table cellpadding="0" cellspacing="0" width="65%">
        <tr>
            <td colspan="3">
                ${display_field_for("text")}
            </td>
        </tr>
        <tr>
            <td>
                <input type="radio" name="karma" value="0">Untested</input>
            </td>
            <td>
                <input type="radio" name="karma" value="1">Works for me</input>
            </td>
            <td>
                <input type="radio" name="karma" value="-1">Does not work</input>
            </td>
        </tr>
        <tr>
            <td colspan="3" py:content="submit.display(submit_text)" />
        </tr>
    </table>
</form>
