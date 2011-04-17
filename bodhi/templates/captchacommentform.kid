<form xmlns:py="http://purl.org/kid/ns#"
    name="${name}"
    action="${tg.url('/captcha_comment')}"
    method="${method}"
    py:attrs="form_attrs" width="100%">

    <div py:for="field in hidden_fields"
         py:replace="field.display(value_for(field), **params_for(field))" />

    <table cellpadding="0" cellspacing="0" width="45%">
        <tr>
            <td colspan="3">
                Tip: <a href="${tg.url('/login')}">Login</a> to impact how quickly this update gets pushed or unpushed.
            </td>
        </tr>
        <tr>
            <td colspan="3">
                ${display_field_for("author")}
            </td>
        </tr>
        <tr>
            <td colspan="3">
                ${display_field_for("text")}
            </td>
        </tr>
        <tr>
            <td>
                <label for="untested"><input id="untested" type="radio" name="karma" value="0" checked="true"/>Untested</label>
            </td>
            <td>
                <label for="wfm"><input type="radio" name="karma" value="1" id="wfm"/>Works for me</label>
            </td>
            <td>
                <label for="dnw"><input id="dnw" type="radio" name="karma" value="-1"/>Does not work</label>
            </td>
        </tr>
        <tr>
            <td colspan="3">
                ${display_field_for("captcha")}
            </td>
        </tr>
        <tr>
            <td colspan="3" py:content="submit.display(submit_text)" />
        </tr>
    </table>
    <div py:if="value.has_key('karma')">
      <script type="text/javascript">
        if( ${value['karma']} == 1 ){
            $('#wfm').attr('checked', true);
        } else if( ${value['karma']} == -1 ){
            $('#dnw').attr('checked', true);
        }
      </script>
    </div>
</form>
